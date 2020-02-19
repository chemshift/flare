import pytest
import numpy as np
import pickle

from flare.env import AtomicEnvironment
from flare.struc import Structure
from flare.kernels.kernels import two_plus_three_body, two_plus_three_body_grad
from flare.gp import GaussianProcess
from flare.mgp.mgp_en import MappedGaussianProcess
from flare.gp_from_aimd import TrajectoryTrainer
from flare.kernels.mc_simple import two_plus_three_body_mc, \
    two_plus_three_body_mc_grad
from json import loads
from flare.env import AtomicEnvironment
import os
from .test_mgp_unit import all_mgp, all_gp, get_random_structure
from .fake_gp import get_gp

@pytest.fixture
def methanol_gp():
    the_gp = GaussianProcess(kernel=two_plus_three_body_mc,
                             kernel_grad=two_plus_three_body_mc_grad,
                             hyps=np.array([3.75996759e-06, 1.53990678e-02,
                                            2.50624782e-05, 5.07884426e-01,
                                            1.70172923e-03]),
                             cutoffs=np.array([7, 7]),
                             hyp_labels=['l2', 's2', 'l3', 's3', 'n0'],
                             maxiter=1,
                             opt_algorithm='L-BFGS-B')
    with open('./test_files/methanol_envs.json') as f:
        dicts = [loads(s) for s in f.readlines()]

    for cur_dict in dicts:
        force = cur_dict['forces']
        env = AtomicEnvironment.from_dict(cur_dict)
        the_gp.add_one_env(env, force)

    the_gp.set_L_alpha()

    return the_gp


@pytest.fixture
def fake_gp():
    return GaussianProcess(kernel=two_plus_three_body,
                           kernel_grad=two_plus_three_body_grad,
                           hyps=np.array([1]),
                           cutoffs=np.array([]))


def test_instantiation_of_trajectory_trainer(fake_gp):
    a = TrajectoryTrainer(frames=[], gp=fake_gp)

    assert isinstance(a, TrajectoryTrainer)

    fake_gp.parallel = True
    _ = TrajectoryTrainer([], fake_gp, parallel=True, calculate_energy=True)
    _ = TrajectoryTrainer([], fake_gp, parallel=True, calculate_energy=False)

    fake_gp.parallel = False
    _ = TrajectoryTrainer([], fake_gp, parallel=False, calculate_energy=True)
    _ = TrajectoryTrainer([], fake_gp, parallel=False, calculate_energy=False)


def test_load_trained_gp_and_run(methanol_gp):
    with open('./test_files/methanol_frames.json', 'r') as f:
        frames = [Structure.from_dict(loads(s)) for s in f.readlines()]

    tt = TrajectoryTrainer(frames,
                           gp=methanol_gp,
                           rel_std_tolerance=0,
                           abs_std_tolerance=0,
                           skip=15)

    tt.run()
    os.system('rm ./gp_from_aimd*')


def test_load_one_frame_and_run():
    the_gp = GaussianProcess(kernel=two_plus_three_body_mc,
                             kernel_grad=two_plus_three_body_mc_grad,
                             hyps=np.array([3.75996759e-06, 1.53990678e-02,
                                            2.50624782e-05, 5.07884426e-01,
                                            1.70172923e-03]),
                             cutoffs=np.array([7, 7]),
                             hyp_labels=['l2', 's2', 'l3', 's3', 'n0'],
                             maxiter=1,
                             opt_algorithm='L-BFGS-B')

    with open('./test_files/methanol_frames.json', 'r') as f:
        frames = [Structure.from_dict(loads(s)) for s in f.readlines()]

    tt = TrajectoryTrainer(frames,
                           gp=the_gp, shuffle_frames=True,
                           rel_std_tolerance=0,
                           abs_std_tolerance=0,
                           skip=15)

    tt.run()
    os.system('rm ./gp_from_aimd*')


def test_seed_and_run():
    the_gp = GaussianProcess(kernel=two_plus_three_body_mc,
                             kernel_grad=two_plus_three_body_mc_grad,
                             hyps=np.array([3.75996759e-06, 1.53990678e-02,
                                            2.50624782e-05, 5.07884426e-01,
                                            1.70172923e-03]),
                             cutoffs=np.array([7, 7]),
                             hyp_labels=['l2', 's2', 'l3', 's3', 'n0'],
                             maxiter=1,
                             opt_algorithm='L-BFGS-B')

    with open('./test_files/methanol_frames.json', 'r') as f:
        frames = [Structure.from_dict(loads(s)) for s in f.readlines()]

    with open('./test_files/methanol_envs.json', 'r') as f:
        data_dicts = [loads(s) for s in f.readlines()[:6]]
        envs = [AtomicEnvironment.from_dict(d) for d in data_dicts]
        forces = [np.array(d['forces']) for d in data_dicts]
        seeds = list(zip(envs, forces))

    tt = TrajectoryTrainer(frames,
                           gp=the_gp, shuffle_frames=True,
                           rel_std_tolerance=0,
                           abs_std_tolerance=0,
                           skip=10,
                           pre_train_seed_envs=seeds,
                           pre_train_seed_frames=[frames[-1]],
                           max_atoms_from_frame=4,
                           output_name='meth_test',
                           model_format='pickle',
                           checkpoint_interval=1,
                           pre_train_atoms_per_element={'H': 1})

    tt.run()

    with open('meth_test_model.pickle', 'rb') as f:
        new_gp = pickle.load(f)

    test_env = envs[0]

    for d in [0, 1, 2]:
        assert np.all(the_gp.predict(x_t=test_env, d=d) ==
                      new_gp.predict(x_t=test_env, d=d))

    os.system('rm ./meth_test*')


def test_mgp_gpfa(all_mgp, all_gp):
    '''
    Ensure that passing in an MGP also works for the trajectory trainer
    :param all_mgp:
    :param all_gp:
    :return:
    '''

    gp_model  = get_gp('3', 'mc', False)
    gp_model.set_L_alpha()

    grid_num_2 = 5
    grid_num_3 = 3
    lower_cut = 0.01
    two_cut = gp_model.cutoffs[0]
    three_cut = gp_model.cutoffs[1]
    # set struc params. cell and masses arbitrary?
    mapped_cell = np.eye(3) * 2
    struc_params = {'species': [1, 2],
                    'cube_lat': mapped_cell,
                    'mass_dict': {'0': 27, '1': 16}}

    # grid parameters
    train_size = len(gp_model.training_data)
    grid_params = {'bodies': [2],
                   'cutoffs': gp_model.cutoffs,
                   'bounds_2': [[lower_cut], [two_cut]],
                   'bounds_3': [[lower_cut, lower_cut, lower_cut],
                                [three_cut, three_cut, three_cut]],
                   'grid_num_2': grid_num_2,
                   'grid_num_3': [grid_num_3, grid_num_3, grid_num_3],
                   'svd_rank_2': np.min((grid_num_2, 3 * train_size)),
                   'svd_rank_3': np.min((grid_num_3 ** 3, 3 * train_size)),
                   'load_grid': None,
                   'update': False}

    struc_params = {'species': [1, 2],
                    'cube_lat': np.eye(3) * 2,
                    'mass_dict': {'0': 27, '1': 16}}

    mgp_model = MappedGaussianProcess(grid_params, struc_params)

    mgp_model.build_map(gp_model)
    nenv = 10
    cell = np.eye(3)
    unique_species = gp_model.training_data[0].species
    struc, f = get_random_structure(cell, unique_species, nenv)

    struc.forces = np.array(f)

    frames = [struc]


    tt = TrajectoryTrainer(frames, mgp_model)
    print(mgp_model)
    assert tt.mgp is True
    tt.run()
