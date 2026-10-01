import numpy as np
from scipy.stats import percentileofscore

class ScoreFuser:
    def __init__(self):
        # We store the normal scores to map future scores to percentiles
        self.val_scores = {}
        
    def fit(self, model_names, val_scores_list):
        """
        val_scores_list: list of normal arrays (one for each model)
        """
        for name, scores in zip(model_names, val_scores_list):
            self.val_scores[name] = np.sort(scores)
            
    def score(self, model_names, test_scores_list):
        """
        Converts each test score to a percentile based on val distribution,
        then averages them.
        """
        percentiles = []
        for name, scores in zip(model_names, test_scores_list):
            # For each score, what percentage of val_scores is it strictly greater than?
            # We use searchsorted to quickly find the insertion index
            val_dist = self.val_scores[name]
            # normalized to 0-100
            perc = np.searchsorted(val_dist, scores) / len(val_dist) * 100
            percentiles.append(perc)
            
        # Average the percentiles
        return np.mean(percentiles, axis=0)
