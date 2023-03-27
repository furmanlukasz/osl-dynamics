"""
DyNeMo: Soft Mixture Simulation
===============================

In this tutorial we will train a DyNeMo on simulated data which contains a mixture of modes. This tutorial covers:

1. Simulating Data
2. Training DyNeMo
3. Getting Inferred Model Parameters

Note, this webpage does not contain the output of running each cell. See `OSF <https://osf.io/w3g7a>`_ for the expected output.
"""

#%%
# Simulating Data
# ^^^^^^^^^^^^^^^
# 
# Let's start by simulating some training data.
# 
# Soft mixture simulation
# ***********************
# 
# We can use the `simulation.MixedSine_MVN <https://osl-dynamics.readthedocs.io/en/latest/autoapi/osl_dynamics/simulation/sm/index.html#osl_dynamics.simulation.sm.MixedSine_MVN>`_ class to simulate a soft mixture of multivariate normals. This simulation (with zero mean) is very close to the DyNeMo model:
# 
# .. math::
#     m_t = 0, \\
#     C_t = \displaystyle\sum_j \alpha_{jt} D_j,
# 
# where :math:`\alpha_{jt}` are mixing coefficients and :math:`D_j` are mode covariances. The `simulation.MixedSine_MVN <https://osl-dynamics.readthedocs.io/en/latest/autoapi/osl_dynamics/simulation/sm/index.html#osl_dynamics.simulation.sm.MixedSine_MVN>`_ class generates the mixing coefficients with sinusoidal logits. I.e. :math:`\alpha_{jt} = \{ \mathrm{softmax}(\theta_t) \}_j`, where :math:`\theta_{jt} = A_j \sin (2 \pi f_j t + \phi_j)`. Let's first simulate some data then we'll look at these components in more detail.

from osl_dynamics.simulation import MixedSine_MVN

# Simulate data
sim = MixedSine_MVN(
    n_samples=25600,
    n_modes=6,
    n_channels=20,
    relative_activation=[1, 0.5, 0.5, 0.25, 0.25, 0.1],
    amplitudes=[6, 5, 4, 3, 2, 1],
    frequencies=[1, 2, 3, 4, 6, 8],
    sampling_frequency=250,
    means="zero",
    covariances="random",
    random_seed=123,
)

# Standardize (i.e. z-transform)
sim.standardize()

#%%
# We can access the simulated time series via the `sim.time_series` attribute.

sim_ts = sim.time_series
print(sim_ts.shape)

#%%
# We can see we have the expected number of samples and channels. Now let's examine the mode covariances (:math:`D_j`).

from osl_dynamics.utils import plotting

plotting.plot_matrices(sim.covariances)

#%%
# We can see each mode has a unique covariance pattern. Next, let's look at the simulated logits.

plotting.plot_separate_time_series(sim.logits, n_samples=2000)

#%%
# We can see each logit time course is sinsoidal, the shape of each time course is determined by the `relative_activation`, `amplitudes` and `frequencies` argument passed to `simulation.MixedSine_MVN <https://osl-dynamics.readthedocs.io/en/latest/autoapi/osl_dynamics/simulation/sm/index.html#osl_dynamics.simulation.sm.MixedSine_MVN>`_. Finally, let's look at the mixing coefficients, which are generated by applying a softmax transformation to the logits. These can be accessed via the `sim.mode_time_course` attribute.

sim_alp = sim.mode_time_course

plotting.plot_alpha(sim_alp, n_samples=2000)

#%%
# We can see there is a good amount of mixing and dynamics in the mixing coefficients.
# 
# Loading into the Data class
# ***************************
# 
# We can create a Data object by simply passing the simulated numpy array to the `Data class <https://osl-dynamics.readthedocs.io/en/latest/autoapi/osl_dynamics/data/base/index.html#osl_dynamics.data.base.Data>`_.

from osl_dynamics.data import Data

training_data = Data(sim_ts)

#%%
# Training DyNeMo
# ^^^^^^^^^^^^^^^
# 
# Create the model
# ****************
# 
# Next, let's create a DyNeMo model. We do this by creating a Config object. See the `API reference guide <https://osl-dynamics.readthedocs.io/en/latest/autoapi/osl_dynamics/models/dynemo/index.html#osl_dynamics.models.dynemo.Config>`_ for a list of the arguments that can be passed to DyNeMo's Config class.

from osl_dynamics.models.dynemo import Config

config = Config(
    n_modes=6,
    n_channels=20,
    sequence_length=200,
    inference_n_units=64,
    inference_normalization="layer",
    model_n_units=64,
    model_normalization="layer",
    learn_alpha_temperature=True,
    initial_alpha_temperature=1.0,
    learn_means=False,
    learn_covariances=True,
    do_kl_annealing=True,
    kl_annealing_curve="tanh",
    kl_annealing_sharpness=10,
    n_kl_annealing_epochs=100,
    batch_size=16,
    learning_rate=0.01,
    n_epochs=200,
)

#%%
# Note, we are using the same number of modes as we did in the simulation. Now we build the DyNeMo model.

from osl_dynamics.models.dynemo import Model

model = Model(config)
model.summary()

#%%
# Train the model
# ***************
# 
# Now we have created the model we can train it on the simulated data. This can be done using the `fit` method by simply passing the Data object. In this tutorial, we will also pass `use_tqdm=True`, which will tell the `fit` method to use a tqdm progress bar instead of the default TensorFlow progress bar. This argument is only for visualisation the progress bar, it does not affect the training.

print("Training model:")
model.fit(training_data, use_tqdm=True)

#%%
# Getting the Inferred Parameters
# ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# 
# Now we have trained the model, let's look at the inferred parameters, in particular the inferred mixing coefficients. We can get these using the `get_alpha` method of the model.

inf_alp = model.get_alpha(training_data)

#%%
# There is a trivial identifiability problem with DyNeMo where the mode label can be switched. I.e. the ordering of the modes can be changed without affecting the loss function. Therefore, before we compare the inferred mixing coefficients to the simulation, we need to make sure the ordering matches. osl-dynamics has the `inference.modes.match_modes <https://osl-dynamics.readthedocs.io/en/latest/autoapi/osl_dynamics/inference/modes/index.html#osl_dynamics.inference.modes.match_modes>`_ function, which re-orders the modes to achieve the highest Pearson correlation between pairs. Let's use this function to re-order the inferred mixing coefficients.

from osl_dynamics.inference import modes

sim_alp, inf_alp = modes.match_modes(sim_alp, inf_alp)

#%%
# Finally, let's compare the inferred and simulated mixing coefficients.

# Compare the inferred mode time course to the ground truth
plotting.plot_alpha(
    sim_alp,
    n_samples=2000,
    title="Ground Truth",
    y_labels=r"$\alpha_{jt}$",
)
plotting.plot_alpha(
    inf_alp,
    n_samples=2000,
    title="DyNeMo",
    y_labels=r"$\alpha_{jt}$",
)

#%%
# We can see these is a good correspondence between the inferred and simulated mixing coefficients, demonstrating DyNeMo's ability to learn a mixture of modes.
# 
# Wrap up
# ^^^^^^^
# 
# - We have some how to simulate a soft mixture of multivariate normals.
# - We have trained DyNeMo on simulation data.
# - We have shown DyNeMo can learn a soft mixture.
