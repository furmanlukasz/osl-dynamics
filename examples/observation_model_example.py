"""Example script for fitting the observation model to HMM data.

- A seed is set for the random number generators for reproducibility.
"""

print("Setting up")
from pathlib import Path

import numpy as np
from vrad import data
from vrad.inference import tf_ops
from vrad.models import GO
from vrad.simulation import MixedHSMMSimulation
from vrad.utils import plotting

# GPU settings
tf_ops.gpu_growth()

# Settings
n_samples = 25600
observation_error = 0.2
gamma_shape = 20
gamma_scale = 10

n_states = 5
sequence_length = 200
batch_size = 16

n_epochs = 20

learn_alpha_scaling = False
normalize_covariances = False

learning_rate = 0.01

# Load state transition probability matrix and covariances of each state
example_file_directory = Path(__file__).parent / "files"
cov = np.load(example_file_directory / "hmm_cov.npy")

# Mixtures of states to include in the simulation
mixed_state_vectors = np.array(
    [[0.5, 0.5, 0, 0, 0], [0, 0.3, 0, 0.7, 0], [0, 0, 0.6, 0.4, 0]]
)

# Simulate data
print("Simulating data")
sim = MixedHSMMSimulation(
    n_samples=n_samples,
    mixed_state_vectors=mixed_state_vectors,
    gamma_shape=gamma_shape,
    gamma_scale=gamma_scale,
    zero_means=True,
    covariances=cov,
    observation_error=observation_error,
    random_seed=123,
)
sim.standardize()
meg_data = data.PreprocessedData(sim)
n_channels = meg_data.n_channels

# Prepare dataset
training_datasets = meg_data.covariance_training_datasets(
    [sim.state_time_course],
    sequence_length,
    batch_size,
)

# Build model
model = GO(
    n_channels=n_channels,
    n_states=n_states,
    sequence_length=sequence_length,
    learn_alpha_scaling=learn_alpha_scaling,
    normalize_covariances=normalize_covariances,
    learning_rate=learning_rate,
)
model.summary()

print("Training model")
history = model.fit(training_datasets[0], epochs=n_epochs)

covariances = model.get_covariances()
plotting.plot_matrices(covariances - sim.covariances, filename="cov_diff.png")

# Delete the temporary folder holding the data
meg_data.delete_dir()
