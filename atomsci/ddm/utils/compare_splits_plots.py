import argparse
import pandas as pd
import os
import numpy as np

from atomsci.ddm.pipeline import chem_diversity as cd
from atomsci.ddm.pipeline import MultitaskScaffoldSplit as mss

import seaborn as sns
from matplotlib import pyplot
from rdkit import Chem
from rdkit.Chem import AllChem
import umap

class SplitStats:
    """
    This object manages a dataset and a given split dataframe.
    """
    def __init__(self, total_df, split_df, smiles_col, id_col, response_cols):
        """
        Calculates compount to compount Tanomoto distances between training and
        test subsets. Counts the number of samples for each subset, for each task
        and calculates the train_frac, valid_frac, and test_frac.

        Args:
            total_df (DataFrame): Pandas DataFrame.
            split_df (DataFrame): AMPL split data frame. Must contain 
                'cmpd_id' and 'subset' columns.
            smiles_col (str): SMILES column in total_df.
            id_col (str): ID column in total_df.
            response_cols (str): Response columns in total_df.
        """
        self.smiles_col = smiles_col
        self.id_col = id_col
        self.response_cols = response_cols
        self.total_df = total_df
        self.split_df = split_df

        self.train_df, self.test_df, self.valid_df = split(self.total_df, self.split_df, self.id_col)

        self.total_y, self.total_w = mss.make_y_w(self.total_df, response_cols)
        self.train_y, self.train_w = mss.make_y_w(self.train_df, response_cols)
        self.test_y, self.test_w = mss.make_y_w(self.test_df, response_cols)
        self.valid_y, self.valid_w = mss.make_y_w(self.valid_df, response_cols)

        self.dists = self._get_dists()

        self.train_fracs, self.valid_fracs, self.test_fracs = self._split_ratios()

    def _get_dists(self):
        '''
        Calculate pairwise compound distances between training and test subsets.

        Args:
            None

        Returns:
            Array of floats. Pairwise Tanimoto distances between training and test subsets.
        '''
        return cd.calc_dist_smiles('ECFP', 'tanimoto', self.train_df[self.smiles_col].values, 
                    self.test_df[self.smiles_col].values)
    
    def _split_ratios(self):
        '''
        Calculates the fraction of samples belonging to training, validation, and test subsets.

        Args:
            None

        Returns:
            train_fracs (array of flots), valid_fracs (array of floats), test_fracs (array of floats)
        '''
        train_fracs = np.sum(self.train_w, axis=0)/np.sum(self.total_w, axis=0)
        valid_fracs = np.sum(self.valid_w, axis=0)/np.sum(self.total_w, axis=0)
        test_fracs = np.sum(self.test_w, axis=0)/np.sum(self.total_w, axis=0)
    
        return train_fracs, valid_fracs, test_fracs

    def print_stats(self):
        '''
        Prints useful statistics to stdout
        '''
        print("dist mean: %0.2f, median: %0.2f, std: %0.2f"%\
            (np.mean(self.dists), np.median(self.dists), np.std(self.dists)))
        print("train frac mean: %0.2f, median: %0.2f, std: %0.2f"%\
            (np.mean(self.train_fracs), np.median(self.train_fracs), np.std(self.train_fracs)))
        print("test frac mean: %0.2f, median: %0.2f, std: %0.2f"%\
            (np.mean(self.test_fracs), np.median(self.test_fracs), np.std(self.test_fracs)))
        print("valid frac mean: %0.2f, median: %0.2f, std: %0.2f"%\
            (np.mean(self.valid_fracs), np.median(self.valid_fracs), np.std(self.valid_fracs)))


    def dist_hist_plot(self, dist_path=''):
        """
        Creates a histogram of pairwise Tanimoto distances between training
        and test sets

        Args:
            dist_path (str): Optional Where to save the plot. The string '_dist_hist' will be
                appended to this input
        """
        # plot compound distance histogram
        pyplot.figure()
        g = sns.distplot(self.dists, kde=False)
        g.set_xlabel('Tanimoto Distance',fontsize=13)
        g.set_ylabel('# Compound Pairs',fontsize=13)
        
        if len(dist_path) > 0:
            save_figure(dist_path+'_dist_hist')

    def umap_plot(self, dist_path=''):
        """
        Plots the first 10000 samples in Umap space using Morgan Fingerprints

        Args:
            dist_path (str): Optional Where to save the plot. The string '_umap_scatter' will be
                appended to this input
        """
        # umap of a subset
        sub_sample_df = self.split_df.loc[np.random.permutation(self.split_df.index)[:10000]]
        # add subset column to total_df
        sub_total_df = sub_sample_df[['cmpd_id', 'subset']].merge(
            self.total_df, left_on='cmpd_id', right_on=self.id_col, how='inner')
        fp = [AllChem.GetMorganFingerprintAsBitVect(Chem.MolFromSmiles(s), 2, 1024) for s in sub_total_df[self.smiles_col]]
        fp_array = np.array(fp)

        embedded = umap.UMAP().fit_transform(fp_array)
        sub_total_df['x'] = embedded[:,0]
        sub_total_df['y'] = embedded[:,1]
        pyplot.figure()
        sns.scatterplot(x='x', y='y', hue='subset', data=sub_total_df)
        if len(dist_path) > 0:
            save_figure(dist_path+'_umap_scatter')

    def subset_frac_plot(self, dist_path=''):
        """
        Makes a box plot of the subset fractions

        Args:
            dist_path (str): Optional Where to save the plot. The string '_frac_box' will be
                appended to this input
        """
        dicts = []
        for f in self.train_fracs:
            dicts.append({'frac':f, 'subset':'train'})
        for f in self.test_fracs:
            dicts.append({'frac':f, 'subset':'test'})
        for f in self.valid_fracs:
            dicts.append({'frac':f, 'subset':'valid'})

        frac_df = pd.DataFrame.from_dict(dicts)

        pyplot.figure()
        g = sns.boxplot(x='subset', y='frac', data=frac_df)
        if len(dist_path) > 0:
            save_figure(dist_path+'_frac_box')

    def make_all_plots(self, dist_path=''):
        """
        Makes a series of diagnostic plots

        Args:
            dist_path (str): Optional Where to save the plot. The string '_frac_box' will be
                appended to this input
        """

        # histogram of compound distances between training and test subsets
        self.dist_hist_plot(dist_path)

        # umap on ecfp fingerprints. visualizes clusters of training/valid/testing split
        self.umap_plot(dist_path)

        # box plot of fractions
        self.subset_frac_plot(dist_path)

def split(total_df, split_df, id_col):
    '''
    Splits a dataset into training, test and validation sets using a given split.

    Args:
        total_df (DataFrame): A pandas dataframe.
        split_df (DataFrame): A split dataframe containing 'cmpd_id' and 'subset' columns.
        id_col (str): The ID column in total_df

    Returns:
        (DataFrame, DataFrame, DataFrame): Three dataframes for train, test, and valid 
            respectively.
    '''
    train_df = total_df[total_df[id_col].isin(split_df[split_df['subset']=='train']['cmpd_id'])]
    test_df = total_df[total_df[id_col].isin(split_df[split_df['subset']=='test']['cmpd_id'])]
    valid_df = total_df[total_df[id_col].isin(split_df[split_df['subset']=='valid']['cmpd_id'])]
    
    return train_df, test_df, valid_df

def save_figure(filename):
    '''
    Saves a figure to disk. Saves both png and svg formats.

    Args:
        filename (str): The name of the figure.
    '''
    pyplot.tight_layout()
    pyplot.savefig(filename+'.png')
    pyplot.savefig(filename+'.svg')

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('csv', help='Source dataset csv.')
    parser.add_argument('id_col', help='ID column for source dataset')
    parser.add_argument('smiles_col', help='SMILES column for source dataset')
    parser.add_argument('split_a', help='Split A. A split csv generated by AMPL')
    parser.add_argument('split_b', help='Split B. A split csv generated by AMPL')

    parser.add_argument('output_dir', help='Output directory for plots')

    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()

    df = pd.read_csv(args.csv, dtype={args.id_col:str})

    split_a = pd.read_csv(args.split_a, dtype={'cmpd_id':str})
    ss = SplitStats(df, split_a, smiles_col=args.smiles_col, id_col=args.id_col)
    ss.make_all_plots(dist_path=os.path.join(args.output_dir, 'split_a'))


    split_b = pd.read_csv(args.split_b, dtype={'cmpd_id':str})
    ss = SplitStats(df, split_b, smiles_col=args.smiles_col, id_col=args.id_col)
    ss.make_all_plots(dist_path=os.path.join(args.output_dir, 'split_b'))