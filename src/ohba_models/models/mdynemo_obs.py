"""Multi-Dynamic Network Modes (M-DyNeMo) observation model.

"""

from dataclasses import dataclass

import numpy as np
import tensorflow as tf
from tensorflow.keras import layers
from ohba_models.models.mod_base import BaseModelConfig, ModelBase
from ohba_models.inference.layers import (
    LogLikelihoodLossLayer,
    MeanVectorsLayer,
    DiagonalMatricesLayer,
    CorrelationMatricesLayer,
    MixVectorsLayer,
    MixMatricesLayer,
    MatMulLayer,
)


@dataclass
class Config(BaseModelConfig):
    """Settings for M-DyNeMo observation model.

    Parameters
    ----------
    n_modes : int
        Number of modes.
    n_channels : int
        Number of channels.
    sequence_length : int
        Length of sequence passed to the generative model.

    learn_means : bool
        Should we make the mean vectors for each mode trainable?
    learn_covariances : bool
        Should we make the covariance matrix for each mode trainable?
    initial_means : np.ndarray
        Initialisation for mean vectors.
    initial_covariances : np.ndarray
        Initialisation for mode covariances.

    batch_size : int
        Mini-batch size.
    learning_rate : float
        Learning rate.
    gradient_clip : float
        Value to clip gradients by. This is the clipnorm argument passed to
        the Keras optimizer. Cannot be used if multi_gpu=True.
    n_epochs : int
        Number of training epochs.
    optimizer : str or tensorflow.keras.optimizers.Optimizer
        Optimizer to use. 'adam' is recommended.
    multi_gpu : bool
        Should be use multiple GPUs for training?
    strategy : str
        Strategy for distributed learning.
    """

    multiple_dynamics: bool = True

    # Observation model parameters
    learn_means: bool = None
    learn_stds: bool = None
    learn_fcs: bool = None
    initial_means: np.ndarray = None
    initial_stds: np.ndarray = None
    initial_fcs: np.ndarray = None

    def __post_init__(self):
        self.validate_observation_model_parameters()
        self.validate_dimension_parameters()
        self.validate_training_parameters()

    def validate_observation_model_parameters(self):
        if (
            self.learn_means is None
            or self.learn_stds is None
            or self.learn_fcs is None
        ):
            raise ValueError("learn_means, learn_stds and learn_fcs must be passed.")


class Model(ModelBase):
    """M-DyNeMo observation model class.

    Parameters
    ----------
    config : ohba_models.models.mdynemo_obs.Config
    """

    def build_model(self):
        """Builds a keras model."""
        self.model = _model_structure(self.config)

    def get_means_stds_fcs(self):
        """Get the mean, standard devation and functional connectivity of each mode.

        Returns
        -------
        means : np.ndarray
            Mode means.
        stds : np.ndarray
            Mode standard deviations.
        fcs : np.ndarray
            Mode functional connectivities.
        """
        return get_means_stds_fcs(self.model)

    def set_means_stds_fcs(self, means, stds, fcs, update_initializer=True):
        """Set the means, standard deviations, functional connectivities of each mode.

        Parameters
        ----------
        means: np.ndarray
            Mode means with shape (n_modes, n_channels).
        stds: np.ndarray
            Mode standard deviations with shape (n_modes, n_channels) or
            (n_modes, n_channels, n_channels).
        fcs: np.ndarray
            Mode functional connectivities with shape (n_modes, n_channels, n_channels).
        update_initializer: bool
            Do we want to use the passed parameters when we re_initialize
            the model?
        """
        set_means_stds_fcs(self.model, means, stds, fcs, update_initializer)


def _model_structure(config):

    # Layers for inputs
    data = layers.Input(shape=(config.sequence_length, config.n_channels), name="data")
    alpha = layers.Input(shape=(config.sequence_length, config.n_modes), name="alpha")
    gamma = layers.Input(shape=(config.sequence_length, config.n_modes), name="gamma")

    # Observation model:
    # - We use a multivariate normal with a mean vector and covariance matrix for
    #   each mode as the observation model.
    # - We calculate the likelihood of generating the training data with alpha
    #   and the observation model.

    # Layers
    means_layer = MeanVectorsLayer(
        config.n_modes,
        config.n_channels,
        config.learn_means,
        config.initial_means,
        name="means",
    )
    stds_layer = DiagonalMatricesLayer(
        config.n_modes,
        config.n_channels,
        config.learn_stds,
        config.initial_stds,
        name="stds",
    )
    fcs_layer = CorrelationMatricesLayer(
        config.n_modes,
        config.n_channels,
        config.learn_fcs,
        config.initial_fcs,
        name="fcs",
    )
    mix_means_layer = MixVectorsLayer(name="mix_means")
    mix_stds_layer = MixMatricesLayer(name="mix_stds")
    mix_fcs_layer = MixMatricesLayer(name="mix_fcs")
    matmul_layer = MatMulLayer(name="cov")
    ll_loss_layer = LogLikelihoodLossLayer(name="ll_loss")

    # Data flow
    mu = means_layer(data)  # data not used
    E = stds_layer(data)  # data not used
    D = fcs_layer(data)  # data not used

    m = mix_means_layer([alpha, mu])
    G = mix_stds_layer([alpha, E])
    F = mix_fcs_layer([gamma, D])
    C = matmul_layer([G, F, G])

    ll_loss = ll_loss_layer([data, m, C])

    return tf.keras.Model(
        inputs=[data, alpha, gamma], outputs=[ll_loss], name="M-DyNeMo-Obs"
    )


def get_means_stds_fcs(model):
    means_layer = model.get_layer("means")
    stds_layer = model.get_layer("stds")
    fcs_layer = model.get_layer("fcs")
    return means_layer(1).numpy(), stds_layer(1).numpy(), fcs_layer(1).numpy()


def set_means_stds_fcs(model, means, stds, fcs, update_initializer=True):
    if stds.ndim == 3:
        # Only keep the diagonal as a vector
        stds = np.diagonal(stds, axis1=1, axis2=2)

    means = means.astype(np.float32)
    stds = stds.astype(np.float32)
    fcs = fcs.astype(np.float32)

    # Get layers
    means_layer = model.get_layer("means")
    stds_layer = model.get_layer("stds")
    fcs_layer = model.get_layer("fcs")

    # Transform the matrices to layer weights
    diagonals = stds_layer.bijector.inverse(stds)
    flattened_cholesky_factors = fcs_layer.bijector.inverse(fcs)

    # Set values
    means_layer.vectors.assign(means)
    stds_layer.diagonals.assign(diagonals)
    fcs_layer.flattened_cholesky_factors.assign(flattened_cholesky_factors)

    # Update initialisers
    if update_initializer:
        means_layer.initial_value = means
        stds_layer.initial_value = stds
        fcs_layer.initial_value = fcs

        stds_layer.initial_diagonals = diagonals
        fcs_layer.initial_flattened_cholesky_factors = flattened_cholesky_factors

        means_layer.vectors_initializer.initial_value = means
        stds_layer.diagonals_initializer.initial_value = diagonals
        fcs_layer.flattened_cholesky_factors_initializer.initial_value = (
            flattened_cholesky_factors
        )
