import numpy as np
import os
import torch
from torch.utils.tensorboard import SummaryWriter

from utils.analysis import compute_model_fixed_points, compute_projected_hidden_states_pca
from utils.env import create_biased_choice_worlds
from utils.hooks import create_hook_fns_analyze
from utils.run import load_checkpoint, run_envs


def main():

    run_dir = 'rnn, num_layers=1, hidden_size=100, param_init=default_2020-02-24 09:32:50.187688'
    # run_dir = 'rnn, num_layers=1, hidden_size=10, param_init=eye_2020-02-05 13:56:15.813806'
    train_log_dir = os.path.join('runs', run_dir)

    # collect last checkpoint in the log directory
    checkpoint_paths = [os.path.join(train_log_dir, file_path)
                        for file_path in os.listdir(train_log_dir)
                        if file_path.endswith('.pt')]

    analyze_log_dir = os.path.join('runs', 'analyze_' + run_dir)
    tensorboard_writer = SummaryWriter(log_dir=analyze_log_dir)

    envs = create_biased_choice_worlds(
        num_envs=11,
        tensorboard_writer=tensorboard_writer)

    model, optimizer, grad_step = load_checkpoint(
        checkpoint_path=checkpoint_paths[0],
        tensorboard_writer=tensorboard_writer)

    hook_fns = create_hook_fns_analyze(
        start_grad_step=grad_step)

    analyze_model_output = analyze_model(
        model=model,
        envs=envs,
        optimizer=optimizer,
        hook_fns=hook_fns,
        tensorboard_writer=tensorboard_writer,
        start_grad_step=grad_step,
        num_grad_steps=0,
        tag_prefix='analyze/')

    tensorboard_writer.close()


def analyze_model(model,
                  envs,
                  optimizer,
                  hook_fns,
                  tensorboard_writer,
                  start_grad_step,
                  num_grad_steps=0,
                  tag_prefix='analyze/'):

    if num_grad_steps != 0:
        raise ValueError('Number of gradient steps must be zero!')

    # sets the model in testing mode
    # model.eval()

    avg_reward, avg_correct_choice, run_envs_output = run_envs(
        model=model,
        envs=envs)
    loss = -avg_reward

    analyze_model_output = dict(
        global_step=start_grad_step,
        run_envs_output=run_envs_output
    )

    pca_hidden_states, pca_xrange, pca_yrange, pca = compute_projected_hidden_states_pca(
        hidden_states=run_envs_output['hidden_states'].reshape(
            run_envs_output['hidden_states'].shape[0], -1))

    fixed_points_by_side_by_stimuli = compute_model_fixed_points(
        model=model,
        pca=pca,
        pca_hidden_states=pca_hidden_states,
        session_data=run_envs_output['trial_data'],
        hidden_states=run_envs_output['hidden_states'],
        num_grad_steps=50)

    hook_input = dict(
        loss=loss.item(),
        avg_correct_choice=avg_correct_choice.item(),
        run_envs_output=run_envs_output,
        grad_step=start_grad_step,
        model=model,
        envs=envs,
        optimizer=optimizer,
        pca_hidden_states=pca_hidden_states,
        pca_xrange=pca_xrange,
        pca_yrange=pca_yrange,
        pca=pca,
        fixed_points_by_side_by_stimuli=fixed_points_by_side_by_stimuli,
        tensorboard_writer=tensorboard_writer,
        tag_prefix=tag_prefix)

    for hook_fn in hook_fns[start_grad_step]:
        hook_fn(hook_input)

    return analyze_model_output


if __name__ == '__main__':
    torch.manual_seed(2)
    np.random.seed(2)
    main()
