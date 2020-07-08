import logging
from typing import Union

import mat73
import numpy as np
from vrad import array_ops
from vrad.data.manipulation import prepare
from vrad.data.subject import Subject
from vrad.utils import plotting
from vrad.utils.decorators import auto_repr

_logger = logging.getLogger("VRAD")


class Data:
    """A class for holding time series data for multiple subjects."""

    @auto_repr
    def __init__(
        self, subjects: Union[str, list, np.ndarray], sampling_frequency: float = 1.0,
    ):
        # Validate the subjects
        subjects = self.check(subjects)

        # Number of subjects
        self.n_subjects = len(subjects)

        # Load subjects
        self.subjects = [
            Subject(
                time_series=subjects[i],
                _id=i + 1,
                sampling_frequency=sampling_frequency,
            )
            for i in range(self.n_subjects)
        ]

        # Flag to indicate if the data has been prepared
        self.prepared = False

    def __str__(self):
        return_string = [self.subjects[i].__str__() for i in range(self.n_subjects)]
        return "\n\n".join(return_string)

    def check(self, subjects: Union[str, list, np.ndarray]):
        """Checks is the subjects argument has been passed correctly."""

        # Check if only one filename has been pass
        if isinstance(subjects, str):
            subjects = [subjects]

        # If the data array has been passed, check its shape
        if isinstance(subjects, np.ndarray):
            if subjects.ndim != 2 or subjects.ndim != 3:
                raise ValueError(
                    "A 2D (single subject) or 3D (multiple subject) array must "
                    + "be passed."
                )
            if subjects.ndim == 2:
                subjects = subjects[np.newaxis, :, :]

        return subjects

    def add(
        self,
        new_subjects: Union[str, list, np.ndarray],
        sampling_frequency: float = 1.0,
    ):
        """Adds one or more subjects to the data object."""

        # Check new subjects are been passed correctly
        new_subjects = self.check(new_subjects)

        # Add the number of new subjects to the total
        n_new_subjects = len(new_subjects)
        self.n_subjects += n_new_subjects

        # Create subject objects for the new subjects
        for i in range(n_new_subjects):
            self.subjects.append(
                Subject(
                    time_series=new_subjects[i],
                    _ids=self.n_subjects + i + 1,
                    sampling_frequency=sampling_frequency,
                )
            )

    def remove(self, ids: Union[int, list, np.ndarray]):
        """Removes the subject objects for the subjects specified through ids."""
        if isinstance(ids, int):
            ids = [ids]
        for i in ids:
            del self.subjects[i - 1]

    def prepare(
        self,
        ids: Union[int, list, np.ndarray, str] = "all",
        n_embeddings: int = None,
        n_pca_components: int = None,
        whiten: bool = False,
        random_seed: int = None,
    ):
        """Prepares the subjects specified by ids."""
        if isinstance(ids, int):
            ids = [ids]

        if isinstance(ids, str):
            if ids == "all":
                ids = range(1, self.n_subjects + 1)
            else:
                raise ValueError(f"ids={ids} unknown in data preparation.")

        # Check the time series has not already been prepared
        if self.prepared:
            logging.warning("Data has already been prepared. No changes made.")

        else:
            self.subjects = prepare(
                self.subjects, ids, n_embeddings, n_pca_components, whiten, random_seed,
            )
            self.prepared = True


# noinspection PyPep8Naming
class OSL_HMM:
    """Import and encapsulate OSL HMMs"""

    def __init__(self, filename):
        self.filename = filename
        self.hmm = mat73.loadmat(filename)["hmm"]

        self.state = self.hmm.state
        self.k = int(self.hmm.K)
        self.p = self.hmm.P
        self.dir_2d_alpha = self.hmm.Dir2d_alpha
        self.pi = self.hmm.Pi
        self.dir_alpha = self.hmm.Dir_alpha
        self.prior = self.hmm.prior
        self.train = self.hmm.train

        self.data_files = self.hmm.data_files
        self.epoched_state_path_sub = self.hmm.epoched_statepath_sub
        self.filenames = self.hmm.filenames
        self.f_sample = self.hmm.fsample
        self.gamma = self.hmm.gamma
        self.is_epoched = self.hmm.is_epoched
        self.options = self.hmm.options
        self.state_map_parcel_vectors = self.hmm.statemap_parcel_vectors
        self.subject_state_map_parcel_vectors = self.hmm.statemap_parcel_vectors_persubj
        self.state_maps = self.hmm.statemaps
        self.state_path = self.hmm.statepath.astype(np.int)
        self.subject_indices = self.hmm.subj_inds

        # Aliases
        self.covariances = np.array([state["Gam_rate"] for state in self.state.Omega])
        self.state_time_course = self.gamma
        self.viterbi_path = array_ops.get_one_hot(self.state_path - 1)

    def plot_covariances(self, *args, **kwargs):
        """Wraps plotting.plot_matrices for self.covariances."""
        plotting.plot_matrices(self.covariances, *args, **kwargs)

    def plot_states(self, *args, **kwargs):
        """Wraps plotting.highlight_states for self.viterbi_path."""

        plotting.state_barcode(self.viterbi_path, *args, **kwargs)

    def __str__(self):
        return f"OSL HMM object from file {self.filename}"
