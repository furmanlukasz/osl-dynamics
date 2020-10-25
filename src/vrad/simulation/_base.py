"""Base class for simulations.

"""

from abc import ABC, abstractmethod

import numpy as np
from matplotlib import pyplot as plt
from vrad.utils import plotting
from vrad.utils.decorators import timing


class Simulation(ABC):
    """Class for making the simulation of MEG data easy!

    Parameters
    ----------
    n_samples : int
        Number of time points to generate
    n_channels : int
        Number of channels to create
    n_states : int
        Number of states to simulate
    sim_varying_means : bool
        If False, means will be set to zero.
    covariances : np.ndarray
        covariance matrix for each state, shape should be (n_states, n_channels,
        n_channels).
    observation_error : float
        The standard deviation of noise added to the signal from a normal distribution.
    random_covariance_weights : bool
        Should the simulation use random covariance weights? False gives structured
        covariances.
    simulate : bool
        Should we simulate the time series.
    random_seed : int
        Seed for the random number generator
    """

    def __init__(
        self,
        n_samples: int,
        n_channels: int,
        n_states: int,
        sim_varying_means: bool,
        covariances: np.ndarray,
        observation_error: float,
        random_covariance_weights: bool,
        simulate: bool,
        random_seed: int = None,
    ):

        self.n_samples = n_samples
        self.n_channels = n_channels
        self.n_states = n_states
        self.sim_varying_means = sim_varying_means
        self.random_covariance_weights = random_covariance_weights
        self.observation_error = observation_error

        self.state_time_course = None
        self.covariances = (
            self.create_covariances() if covariances is None else covariances
        )
        self.time_series = None

        # Setup random number generator
        self._rng = np.random.default_rng(random_seed)

        if simulate:
            self.simulate()

    def simulate(self):
        self.state_time_course = self.generate_states()
        self.time_series = self.simulate_data()

    def __array__(self):
        return self.time_series

    def __iter__(self):
        return iter([self.time_series])

    def __getattr__(self, attr):
        if attr == "time_series":
            raise NameError("time_series has not yet been created.")
        if attr[:2] == "__":
            raise AttributeError(f"No attribute called {attr}.")
        return getattr(self.time_series, attr)

    def __len__(self):
        return 1

    @abstractmethod
    def generate_states(self) -> np.ndarray:
        """State generation must be implemented by subclasses.

        """
        pass

    def plot_alphas(self, n_points: int = 1000, filename: str = None):
        """Method for plotting the state time course of a simulation.

        Parameters
        ----------
        n_points : int
            Number of time points to plot.

        Returns
        -------

        """
        plotting.plot_state_time_courses(
            self.state_time_course, n_samples=n_points, filename=filename
        )

    def create_covariances(self, identity_factor: float = 0.0001) -> np.ndarray:
        """Create the covariance matrices for the simulation

        Parameters
        ----------
        identity_factor : float
            Factor by which to scale the identity matrix which is added to the
            covariance.

        Returns
        -------
        covariances_sim : np.array
            The covariance matrices of the simulation

        """
        if self.random_covariance_weights:
            tilde_cov_weights = self._rng.normal(
                size=(self.n_states, self.n_channels, self.n_channels)
            )
        else:
            tilde_cov_weights = np.zeros(
                (self.n_states, self.n_channels, self.n_channels)
            )
            np.fill_diagonal(
                tilde_cov_weights[: self.n_states, : self.n_states, : self.n_states],
                val=1,
            )

        scaled_identity = (
            np.tile(np.eye(self.n_channels), [self.n_states, 1, 1]) * identity_factor
        )
        covariances_sim = (
            tilde_cov_weights @ tilde_cov_weights.transpose([0, 2, 1]) + scaled_identity
        )

        normalisation = np.trace(covariances_sim, axis1=1, axis2=2).reshape((-1, 1, 1))
        covariances_sim /= normalisation
        return covariances_sim

    def simulate_data(self) -> np.ndarray:
        """Simulate a time course of MEG data.

        Returns
        -------
        data_sim : np.array
            A float32 array containing a simulated time course of simulated data.

        """
        if self.sim_varying_means:
            mus_sim = self._rng.normal((self.n_states, self.n_channels))
        else:
            mus_sim = np.zeros((self.n_states, self.n_channels))

        # State time course, shape=(n_samples, n_states)
        # This contains the mixing factors of each states at each time point
        stc = self.state_time_course

        # Array to hold the simulated data
        data_sim = np.zeros((self.n_samples, self.n_channels))

        # Loop through all unique combinations of states
        for alpha in np.unique(stc, axis=0):

            # Mean and covariance for this combination of states
            mu = np.sum(mus_sim * alpha[:, np.newaxis], axis=0)
            sigma = np.sum(self.covariances * alpha[:, np.newaxis, np.newaxis], axis=0)

            # Generate data for the time points that this combination of states is
            # active
            data_sim[np.all(stc == alpha, axis=1)] = self._rng.multivariate_normal(
                mu, sigma, size=np.count_nonzero(np.all(stc == alpha, axis=1))
            )

        # Add an error to the data at all time points
        data_sim += self._rng.normal(scale=self.observation_error, size=data_sim.shape)

        return data_sim.astype(np.float32)

    def standardize(self):
        """Standardizes the data.

        The time series data is z-transformed and the covariances are converted
        to correlation matrices.
        """
        self.means = np.mean(self.time_series, axis=0)
        self.standard_deviations = np.std(self.time_series, axis=0)

        # Z-transform
        self.time_series -= self.means
        self.time_series /= self.standard_deviations

        # Convert covariance matrices to correlation matrices
        self.covariances /= np.outer(
            self.standard_deviations, self.standard_deviations
        )[np.newaxis, ...]

    def plot_data(self, n_points: int = 1000, filename: str = None):
        """Method for plotting simulated data.

        Parameters
        ----------
        n_points : int
            Number of time points to plot.
        """
        n_points = min(n_points, self.n_samples)
        plotting.plot_time_series(
            self.time_series, n_samples=n_points, filename=filename
        )
