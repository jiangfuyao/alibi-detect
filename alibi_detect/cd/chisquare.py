import logging
import numpy as np
from scipy.stats import chisquare
from typing import Callable, Dict, Optional, Tuple, Union
from alibi_detect.cd.base import BaseUnivariateDrift

logger = logging.getLogger(__name__)


class ChiSquareDrift(BaseUnivariateDrift):

    def __init__(self,
                 p_val: float = .05,
                 X_ref: Union[np.ndarray, list] = None,
                 categories_per_feature: Optional[Dict[int, int]] = None,
                 preprocess_X_ref: bool = True,
                 update_X_ref: Optional[Dict[str, int]] = None,
                 preprocess_fn: Optional[Callable] = None,
                 preprocess_kwargs: Optional[dict] = None,
                 correction: str = 'bonferroni',
                 n_features: Optional[int] = None,
                 n_infer: int = 2,
                 input_shape: Optional[tuple] = None,
                 data_type: Optional[str] = None
                 ) -> None:
        """
        Chi-Squared data drift detector with Bonferroni or False Discovery Rate (FDR)
        correction for multivariate data.

        Parameters
        ----------
        p_val
            p-value used for significance of the Chi-Squared test for each feature. If the FDR correction method
            is used, this corresponds to the acceptable q-value.
        X_ref
            Data used as reference distribution. Can be a list for text data which is then turned into an array
            after the preprocessing step.
        categories_per_feature
            Dict with as keys the feature column index and as values the number of possible categorical
            values for that feature. Eg: {0: 5, 1: 9, 2: 7}.
        preprocess_X_ref
            Whether to already preprocess and infer categories and frequencies for reference data.
        update_X_ref
            Reference data can optionally be updated to the last n instances seen by the detector
            or via reservoir sampling with size n. For the former, the parameter equals {'last': n} while
            for reservoir sampling {'reservoir_sampling': n} is passed.
        preprocess_fn
            Function to preprocess the data before computing the data drift metrics.
            Typically a dimensionality reduction technique.
        preprocess_kwargs
            Kwargs for `preprocess_fn`.
        correction
            Correction type for multivariate data. Either 'bonferroni' or 'fdr' (False Discovery Rate).
        n_features
            Number of features used in the Chi-Squared test. No need to pass it if no preprocessing takes place.
            In case of a preprocessing step, this can also be inferred automatically but could be more
            expensive to compute.
        n_infer
            Number of instances used to infer number of features from.
        input_shape
            Shape of input data.
        data_type
            Optionally specify the data type (tabular, image or time-series). Added to metadata.
        """
        super().__init__(
            p_val=p_val,
            X_ref=X_ref,
            preprocess_X_ref=preprocess_X_ref,
            update_X_ref=update_X_ref,
            preprocess_fn=preprocess_fn,
            preprocess_kwargs=preprocess_kwargs,
            correction=correction,
            n_features=n_features,
            n_infer=n_infer,
            input_shape=input_shape,
            data_type=data_type
        )
        # convert from Dict[int, int] to Dict[int, List[int]]
        if isinstance(categories_per_feature, dict):
            self.categories_per_feature = {f: list(np.arange(v)) for f, v in categories_per_feature.items()}
        else:  # infer number of possible categories for each feature from reference data
            X_flat = self.X_ref.reshape(self.X_ref.shape[0], -1)
            self.categories_per_feature = {f: list(np.unique(X_flat[:, f])) for f in range(self.n_features)}

        if update_X_ref is None and preprocess_X_ref:
            # already infer categories and frequencies for reference data
            self.X_ref_count = {f: [(self.X_ref[:, f] == v).sum() for v in vals] for f, vals in
                                self.categories_per_feature.items()}
        else:
            self.X_ref_count = None

    def feature_score(self, X_ref: np.ndarray, X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Compute Chi-Squared test statistic and p-values per feature.

        Parameters
        ----------
        X_ref
            Reference instances to compare distribution with.
        X
            Batch of instances.

        Returns
        -------
        Feature level p-values and Chi-Squared statistics.
        """
        if not self.X_ref_count:  # compute categorical frequency counts for each feature
            X_ref = X_ref.reshape(X_ref.shape[0], -1)
            X_ref_count = {f: [(X_ref[:, f] == v).sum() for v in vals] for f, vals in
                           self.categories_per_feature.items()}
        else:
            X_ref_count = self.X_ref_count
        X = X.reshape(X.shape[0], -1)
        X_count = {f: [(X[:, f] == v).sum() for v in vals] for f, vals in
                   self.categories_per_feature.items()}
        p_val = np.zeros(self.n_features, dtype=np.float32)
        dist = np.zeros_like(p_val)
        for f in range(self.n_features):  # apply Chi-Squared test
            dist[f], p_val[f] = chisquare(X_ref_count[f], f_exp=X_count[f])
        return p_val, dist
