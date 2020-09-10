"""Example script for running inference on simulated HMM data.

- This script sets a seed for the random number generators for reproducibility.
- Should achieve a dice coefficient of ~0.98.
- Takes approximately 2 minutes to train (on compG017).
"""

print("Setting up")
import numpy as np
from vrad import array_ops, data
from vrad.inference import gmm, metrics, states, tf_ops
from vrad.models import RNNGaussian
from vrad.simulation import HMMSimulation
from vrad.utils import plotting

# GPU settings
tf_ops.suppress_messages()
tf_ops.gpu_growth()

# Settings
n_samples = 25000
observation_error = 0.2

n_states = 5
sequence_length = 100
batch_size = 32

do_annealing = True
annealing_sharpness = 5

n_epochs = 100
n_epochs_annealing = 50

dropout_rate_inference = 0.0
dropout_rate_model = 0.0

n_layers_inference = 1
n_layers_model = 1

n_units_inference = 64
n_units_model = 64

learn_means = False
learn_covariances = True

alpha_xform = "softmax"
learn_alpha_scaling = False
normalize_covariances = False

# Load state transition probability matrix and covariances of each state
init_trans_prob = np.load("files/prob_000.npy")
init_cov = np.load("files/state_000.npy")

# Simulate data
print("Simulating data")
sim = HMMSimulation(
    n_samples=n_samples,
    n_states=n_states,
    sim_varying_means=learn_means,
    covariances=init_cov,
    trans_prob=init_trans_prob,
    observation_error=observation_error,
    random_seed=123,
)
meg_data = data.Data(sim)
n_channels = meg_data.n_channels

# Priors
means, covariances = gmm.final_means_covariances(
    meg_data,
    n_states,
    gmm_kwargs={
        "n_init": 1,
        "verbose": 2,
        "verbose_interval": 50,
        "max_iter": 10000,
        "tol": 1e-6,
    },
    retry_attempts=1,
    learn_means=False,
    random_seed=124,
)

# Build model
model = RNNGaussian(
    n_channels=n_channels,
    n_states=n_states,
    sequence_length=sequence_length,
    learn_means=learn_means,
    learn_covariances=learn_covariances,
    initial_means=means,
    initial_covariances=covariances,
    n_layers_inference=n_layers_inference,
    n_layers_model=n_layers_model,
    n_units_inference=n_units_inference,
    n_units_model=n_units_model,
    dropout_rate_inference=dropout_rate_inference,
    dropout_rate_model=dropout_rate_model,
    alpha_xform=alpha_xform,
    learn_alpha_scaling=learn_alpha_scaling,
    normalize_covariances=normalize_covariances,
    do_annealing=do_annealing,
    annealing_sharpness=annealing_sharpness,
    n_epochs_annealing=n_epochs_annealing,
)

model.summary()

# Prepare dataset
training_dataset = meg_data.training_dataset(sequence_length, batch_size)
prediction_dataset = meg_data.prediction_dataset(sequence_length, batch_size)

# Train the model
print("Training model")
history = model.fit(training_dataset, epochs=n_epochs, verbose=0, use_tqdm=True)

# Inferred state probabiliites and state time course
alpha = model.predict_states(prediction_dataset)
stc = states.time_courses(alpha)
stc = np.concatenate(stc)

# Find correspondance to ground truth state time courses
matched_sim_stc, matched_inf_stc = states.match_states(sim.state_time_course, stc)

print("Dice coefficient:", metrics.dice_coefficient(matched_sim_stc, matched_inf_stc))
