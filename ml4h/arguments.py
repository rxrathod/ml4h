# arguments.py
#
# Command Line Arguments for Machine Learning 4 CardioVascular Disease
# Shared by recipes.py and other command-line runnable files.
# These arguments are a bit of a hodge-podge and are used promiscuously throughout these files.
# Sometimes code overwrites user-provided arguments to enforce assumptions or sanity.
#
# October 2018
# Sam Friedman
# sam@broadinstitute.org

# Imports
import os
import sys
import copy
import logging
import hashlib
import argparse
import operator
import datetime
import importlib
import numpy as np
import multiprocessing
from collections import defaultdict
from typing import Set, Dict, List, Optional, Tuple

from ml4h.logger import load_config
from ml4h.TensorMap import TensorMap, TimeSeriesOrder
from ml4h.defines import IMPUTATION_RANDOM, IMPUTATION_MEAN
from ml4h.tensormap.mgb.dynamic import make_mgb_dynamic_tensor_maps
from ml4h.tensormap.tensor_map_maker import generate_categorical_tensor_map_from_file, \
    generate_latent_tensor_map_from_file

from ml4h.models.legacy_models import parent_sort, check_no_bottleneck
from ml4h.tensormap.tensor_map_maker import make_test_tensor_maps, generate_random_pixel_as_text_tensor_maps
from ml4h.models.legacy_models import NORMALIZATION_CLASSES, CONV_REGULARIZATION_CLASSES, DENSE_REGULARIZATION_CLASSES
from ml4h.tensormap.tensor_map_maker import generate_continuous_tensor_map_from_file, generate_random_text_tensor_maps
from ml4h.tensormap.tensor_map_maker import generate_categorical_tensor_map_from_file, generate_latent_tensor_map_from_file


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--mode', default='mlp', help='What would you like to do?')

    # Config arguments
    parser.add_argument(
        "--logging_level", default='INFO', choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Logging level. Overrides any configuration given in the logging configuration file.",
    )

    # Tensor Map arguments
    parser.add_argument('--input_tensors', default=[], nargs='*')
    parser.add_argument('--output_tensors', default=[], nargs='*')
    parser.add_argument('--protected_tensors', default=[], nargs='*')
    parser.add_argument('--tensor_maps_in', default=[], help='Do not set this directly. Use input_tensors')
    parser.add_argument('--tensor_maps_out', default=[], help='Do not set this directly. Use output_tensors')
    parser.add_argument('--tensor_maps_protected', default=[], help='Do not set this directly. Use protected_tensors')

    # Input and Output files and directories
    parser.add_argument(
        '--bigquery_credentials_file', default='/mnt/ml4cvd/projects/jamesp/bigquery/bigquery-viewer-credentials.json',
        help='Path to service account credentials for looking up BigQuery tables.',
    )
    parser.add_argument('--bigquery_dataset', default='broad-ml4cvd.ukbb7089_r10data', help='BigQuery dataset containing tables we want to query.')
    parser.add_argument('--xml_folder', default='/mnt/disks/ecg-rest-xml/', help='Path to folder of XMLs of ECG data.')
    parser.add_argument('--zip_folder', default='/mnt/disks/sax-mri-zip/', help='Path to folder of zipped dicom images.')
    parser.add_argument('--dicoms', default='./dicoms/', help='Path to folder of dicoms.')
    parser.add_argument('--sample_csv', default=None, help='Path to CSV with Sample IDs to restrict tensor paths')
    parser.add_argument('--tsv_style', default='standard', choices=['standard', 'genetics'], help='Format choice for the TSV file produced in output by infer and explore modes.')
    parser.add_argument('--app_csv', help='Path to file used by the recipe')
    parser.add_argument('--tensors', help='Path to folder containing tensors, or where tensors will be written.')
    parser.add_argument('--output_folder', default='./recipes_output/', help='Path to output folder for recipes.py runs.')
    parser.add_argument('--model_file', help='Path to a saved model architecture and weights (hd5).')
    parser.add_argument('--model_files', nargs='*', default=[], help='List of paths to saved model architectures and weights (hd5).')
    parser.add_argument('--model_layers', help='Path to a model file (hd5) which will be loaded by layer, useful for transfer learning.')
    parser.add_argument('--freeze_model_layers', default=False, action='store_true', help='Whether to freeze the layers from model_layers.')
    parser.add_argument('--text_file', default=None, help='Path to a file with text.')
    parser.add_argument(
        '--continuous_file', default=None, help='Path to a file containing continuous values from which a output TensorMap will be made.'
        'Note that setting this argument has the effect of linking the first output_tensors'
        'argument to the TensorMap made from this file.',
    )
    parser.add_argument('--gcs_cloud_bucket', default=None, help='Path to google cloud buckets to be used as output folders for ml4h training and inference runs.')

    # Data selection parameters

    parser.add_argument('--continuous_file_columns', nargs='*', default=[], help='Column headers in file from which continuous TensorMap(s) will be made.')
    parser.add_argument('--continuous_file_normalize', default=False, action='store_true', help='Whether to normalize a continuous TensorMap made from a file.')
    parser.add_argument(
        '--continuous_file_discretization_bounds', default=[], nargs='*', type=float,
        help='Bin boundaries to use to discretize a continuous TensorMap read from a file.',
    )
    parser.add_argument(
        '--categorical_file', default=None, help='Path to a file containing categorical values from which a output TensorMap will be made.'
        'Note that setting this argument has the effect of linking the first output_tensors'
        'argument to the TensorMap made from this file.',
    )
    parser.add_argument(
        '--categorical_file_columns', nargs='*', default=[],
        help='Column headers in file from which categorical TensorMap(s) will be made.',
    )
    parser.add_argument(
        '--latent_input_file', default=None, help=
        'Path to a file containing latent space values from which an input TensorMap will be made.'
        'Note that setting this argument has the effect of linking the first input_tensors'
        'argument to the TensorMap made from this file.',
    )
    parser.add_argument(
        '--latent_output_files', nargs='*', default=[], help=
        'Path to a file containing latent space values from which an input TensorMap will be made.'
        'Note that setting this argument has the effect of linking the first output_tensors'
        'argument to the TensorMap made from this file.',
    )
    parser.add_argument(
        '--categorical_field_ids', nargs='*', default=[], type=int,
        help='List of field ids from which input features will be collected.',
    )
    parser.add_argument(
        '--continuous_field_ids', nargs='*', default=[], type=int,
        help='List of field ids from which continuous real-valued input features will be collected.',
    )
    parser.add_argument('--include_array', default=False, action='store_true', help='Include array idx for UKBB phenotypes.')
    parser.add_argument('--include_instance', default=False, action='store_true', help='Include instances for UKBB phenotypes.')
    parser.add_argument('--min_values', default=10, type=int, help='Per feature size minimum.')
    parser.add_argument('--min_samples', default=3, type=int, help='Min number of samples to require for calculating correlations.')
    parser.add_argument(
        '--max_samples', type=int, default=None,
        help='Max number of samples to use for tensor reporting -- all samples are used if not specified.',
    )
    parser.add_argument('--mri_field_ids', default=['20208', '20209'], nargs='*', help='Field id for MR images.')
    parser.add_argument('--xml_field_ids', default=['20205', '6025'], nargs='*', help='Field id for XMLs of resting and exercise ECG data.')
    parser.add_argument('--max_patients', default=999999, type=int,  help='Maximum number of patient data to read')
    parser.add_argument('--min_sample_id', default=0, type=int, help='Minimum sample id to write to tensor.')
    parser.add_argument('--max_sample_id', default=7000000, type=int, help='Maximum sample id to write to tensor.')
    parser.add_argument('--max_slices', default=999999, type=int, help='Maximum number of dicom slices to read')
    parser.add_argument('--dicom_series', default='cine_segmented_sax_b6', help='Maximum number of dicom slices to read')
    parser.add_argument(
        '--b_slice_force', default=None,
        help='If set, will only load specific b slice for short axis MRI diastole systole tensor maps (i.e b0, b1, b2, ... b10).',
    )
    parser.add_argument(
        '--include_missing_continuous_channel', default=False, action='store_true',
        help='Include missing channels in continuous tensors',
    )
    parser.add_argument(
        '--imputation_method_for_continuous_fields', default=IMPUTATION_RANDOM, help='can be random or mean',
        choices=[IMPUTATION_RANDOM, IMPUTATION_MEAN],
    )

    # Model Architecture Parameters
    parser.add_argument('--x', default=256, type=int, help='x tensor resolution')
    parser.add_argument('--y', default=256, type=int, help='y tensor resolution')
    parser.add_argument('--zoom_x', default=50, type=int, help='zoom_x tensor resolution')
    parser.add_argument('--zoom_y', default=35, type=int, help='zoom_y tensor resolution')
    parser.add_argument('--zoom_width', default=96, type=int, help='zoom_width tensor resolution')
    parser.add_argument('--zoom_height', default=96, type=int, help='zoom_height tensor resolution')
    parser.add_argument('--z', default=48, type=int, help='z tensor resolution')
    parser.add_argument('--t', default=48, type=int, help='Number of time slices')
    parser.add_argument('--mlp_concat', default=False, action='store_true', help='Concatenate input with every multiplayer perceptron layer.')  # TODO: should be the same style as u_connect
    parser.add_argument('--dense_layers', nargs='*', default=[256], type=int, help='List of number of hidden units in neural nets dense layers.')
    parser.add_argument('--dense_regularize_rate', default=0.0, type=float, help='Rate parameter for dense_regularize.')
    parser.add_argument('--dense_regularize', default=None, choices=list(DENSE_REGULARIZATION_CLASSES), help='Type of regularization layer for dense layers.')
    parser.add_argument('--dense_normalize', default=None, choices=list(NORMALIZATION_CLASSES), help='Type of normalization layer for dense layers.')
    parser.add_argument('--activation', default='swish',  help='Activation function for hidden units in neural nets dense layers.')
    parser.add_argument('--conv_layers', nargs='*', default=[32], type=int, help='List of number of kernels in convolutional layers.')
    parser.add_argument(
        '--conv_width', default=[71], nargs='*', type=int,
        help='X dimension of convolutional kernel for 1D models. Filter sizes are specified per layer given by conv_layers and per block given by dense_blocks. Filter sizes are repeated if there are less than the number of layers/blocks.',
    )
    parser.add_argument(
        '--conv_x', default=[3], nargs='*', type=int,
        help='X dimension of convolutional kernel. Filter sizes are specified per layer given by conv_layers and per block given by dense_blocks. Filter sizes are repeated if there are less than the number of layers/blocks.',
    )
    parser.add_argument(
        '--conv_y', default=[3], nargs='*', type=int,
        help='Y dimension of convolutional kernel. Filter sizes are specified per layer given by conv_layers and per block given by dense_blocks. Filter sizes are repeated if there are less than the number of layers/blocks.',
    )
    parser.add_argument(
        '--conv_z', default=[2], nargs='*', type=int,
        help='Z dimension of convolutional kernel. Filter sizes are specified per layer given by conv_layers and per block given by dense_blocks. Filter sizes are repeated if there are less than the number of layers/blocks.',
    )
    parser.add_argument('--conv_dilate', default=False, action='store_true', help='Dilate the convolutional layers.')
    parser.add_argument('--conv_type', default='conv', choices=['conv', 'separable', 'depth'], help='Type of convolutional layer')
    parser.add_argument('--conv_normalize', default=None, choices=list(NORMALIZATION_CLASSES), help='Type of normalization layer for convolutions')
    parser.add_argument('--conv_regularize', default=None, choices=list(CONV_REGULARIZATION_CLASSES), help='Type of regularization layer for convolutions.')
    parser.add_argument('--conv_regularize_rate', default=0.0, type=float, help='Rate parameter for conv_regularize.')
    parser.add_argument('--conv_strides', default=1, type=int, help='Strides to take during convolution')
    parser.add_argument('--conv_without_bias', default=False, action='store_true', help='If True, Do not add bias to convolutional layers.')
    parser.add_argument('--conv_bias_initializer', default='zeros', help='Initializer for the bias vector')
    parser.add_argument('--conv_kernel_initializer', default='glorot_uniform', help='Initializer for the convolutional weight kernel')
    parser.add_argument('--max_pools', nargs='*', default=[], type=int, help='List of maxpooling layers.')
    parser.add_argument('--pool_type', default='max', choices=['max', 'average'], help='Type of pooling layers.')
    parser.add_argument('--pool_x', default=2, type=int, help='Pooling size in the x-axis, if 1 no pooling will be performed.')
    parser.add_argument('--pool_y', default=2, type=int, help='Pooling size in the y-axis, if 1 no pooling will be performed.')
    parser.add_argument('--pool_z', default=1, type=int, help='Pooling size in the z-axis, if 1 no pooling will be performed.')
    parser.add_argument('--padding', default='same', help='Valid or same border padding on the convolutional layers.')
    parser.add_argument('--dense_blocks', nargs='*', default=[32, 32, 32], type=int, help='List of number of kernels in convolutional layers.')
    parser.add_argument('--merge_dimension', default=3, type=int, help='Dimension of the merge layer.')
    parser.add_argument('--merge_dense_blocks', nargs='*', default=[32], type=int, help='List of number of kernels in convolutional merge layer.')
    parser.add_argument('--decoder_dense_blocks', nargs='*', default=[32, 32, 32], type=int, help='List of number of kernels in convolutional decoder layers.')
    parser.add_argument('--encoder_blocks', nargs='*', default=['conv_encode'], help='List of encoding blocks.')
    parser.add_argument('--merge_blocks', nargs='*', default=['concat'], help='List of merge blocks.')
    parser.add_argument('--decoder_blocks', nargs='*', default=['conv_decode', 'dense_decode'], help='List of decoding blocks.')
    parser.add_argument('--block_size', default=3, type=int, help='Number of convolutional layers within a block.')
    parser.add_argument(
        '--u_connect', nargs=2, action='append',
        help='U-Net connect first TensorMap to second TensorMap. They must be the same shape except for number of channels. Can be provided multiple times.',
    )
    parser.add_argument(
        '--pairs', nargs=2, action='append',
        help='TensorMap pairs for paired autoencoder. The pair_loss metric will encourage similar embeddings for each two input TensorMap pairs. Can be provided multiple times.',
    )

    parser.add_argument('--pair_loss', default='contrastive', help='Distance metric between paired embeddings', choices=['euclid', 'cosine', 'contrastive'])
    parser.add_argument('--pair_merge', default='dropout', help='Merging method for paired modality embeddings', choices=['average', 'concat', 'dropout', 'kronecker'])
    parser.add_argument('--pair_loss_weight', type=float, default=1.0, help='Weight on the pair loss term relative to other losses')
    parser.add_argument(
        '--max_parameters', default=50000000, type=int,
        help='Maximum number of trainable parameters in a model during hyperparameter optimization.',
    )
    parser.add_argument('--hidden_layer', default='embed', help='Name of a hidden layer for inspections.')
    parser.add_argument('--language_layer', default='ecg_rest_text', help='Name of TensorMap for learning language models (eg train_char_model).')
    parser.add_argument('--language_prefix', default='ukb_ecg_rest', help='Path prefix for a TensorMap to learn language models (eg train_char_model)')
    parser.add_argument('--text_window', default=32, type=int, help='Size of text window in number of tokens.')
    parser.add_argument('--hd5_as_text', default=None, help='Path prefix for a TensorMap to learn language models from flattened HD5 arrays.')
    parser.add_argument('--attention_heads', default=4, type=int, help='Number of attention heads in Multi-headed attention layers')
    parser.add_argument(
        '--attention_window', default=4, type=int,
        help='For diffusion models, when U-Net representation size is smaller than attention_window '
             'Cross-Attention is applied',
    )
    parser.add_argument(
        '--attention_modulo', default=3, type=int,
        help='For diffusion models, this controls how frequently Cross-Attention is applied. '
             '2 means every other residual block, 3 would mean every third.',
    )
    parser.add_argument(
        '--diffusion_condition_strategy', default='cross_attention',
        choices=['cross_attention', 'concat', 'film'],
        help='For diffusion models, this controls conditional embeddings are integrated into the U-NET',
    )
    parser.add_argument(
        '--diffusion_loss', default='sigmoid',
        help='Loss function to use for diffusion models. Can be sigmoid, mean_absolute_error, or mean_squared_error',
    )
    parser.add_argument(
        '--sigmoid_beta', default=-3, type=float,
        help='Beta to use with sigmoid loss for diffusion models.',
    )
    parser.add_argument(
        '--supervision_scalar', default=0.01, type=float,
        help='For `train_diffusion_supervise` mode, this weights the supervision loss from phenotype prediction on denoised data.',
    )
    parser.add_argument(
         '--transformer_size', default=32, type=int,
         help='Number of output neurons in Transformer encoders and decoders, '
              'the number of internal neurons and the number of layers are set by the --dense_layers',
    )
    parser.add_argument('--pretrain_trainable', default=False, action='store_true', help='If set, do not freeze pretrained layers.')

    # Training and Hyper-Parameter Optimization Parameters
    parser.add_argument('--epochs', default=10, type=int, help='Number of training epochs.')
    parser.add_argument('--batch_size', default=8, type=int, help='Mini batch size for stochastic gradient descent algorithms.')
    parser.add_argument('--train_csv', help='Path to CSV with Sample IDs to reserve for training.')
    parser.add_argument('--valid_csv', help='Path to CSV with Sample IDs to reserve for validation. Takes precedence over valid_ratio.')
    parser.add_argument('--test_csv', help='Path to CSV with Sample IDs to reserve for testing. Takes precedence over test_ratio.')
    parser.add_argument(
        '--valid_ratio', default=0.1, type=float,
        help='Rate of training tensors to save for validation must be in [0.0, 1.0]. '
             'If any of train/valid/test csv is specified, split by ratio is applied on the remaining tensors after reserving tensors given by csvs. '
             'If not specified, default 0.2 is used. If default ratios are used with train_csv, some tensors may be ignored because ratios do not sum to 1.',
    )
    parser.add_argument(
        '--test_ratio', default=0.1, type=float,
        help='Rate of training tensors to save for testing must be in [0.0, 1.0]. '
             'If any of train/valid/test csv is specified, split by ratio is applied on the remaining tensors after reserving tensors given by csvs. '
             'If not specified, default 0.1 is used. If default ratios are used with train_csv, some tensors may be ignored because ratios do not sum to 1.',
    )
    parser.add_argument('--test_steps', default=32, type=int, help='Number of batches to use for testing.')
    parser.add_argument('--training_steps', default=96, type=int, help='Number of training batches to examine in an epoch.')
    parser.add_argument('--validation_steps', default=32, type=int, help='Number of validation batches to examine in an epoch validation.')
    parser.add_argument('--learning_rate', default=0.00005, type=float, help='Learning rate during training.')
    parser.add_argument('--mixup_alpha', default=0, type=float, help='If positive apply mixup and sample from a Beta with this value as shape parameter alpha.')
    parser.add_argument(
        '--label_weights', nargs='*', type=float,
        help='List of per-label weights for weighted categorical cross entropy. If provided, must map 1:1 to number of labels.',
    )
    parser.add_argument(
        '--patience', default=8, type=int,
        help='Early Stopping parameter: Maximum number of epochs to run without validation loss improvements.',
    )
    parser.add_argument(
        '--max_models', default=16, type=int,
        help='Maximum number of models for the hyper-parameter optimizer to evaluate before returning.',
    )
    parser.add_argument('--balance_csvs', default=[], nargs='*', help='Balances batches with representation from sample IDs in this list of CSVs')
    parser.add_argument('--optimizer', default='adam', type=str, help='Optimizer for model training')
    parser.add_argument('--learning_rate_schedule', default=None, type=str, choices=['triangular', 'triangular2', 'cosine_decay'], help='Adjusts learning rate during training.')
    parser.add_argument('--anneal_rate', default=0., type=float, help='Annealing rate in epochs of loss terms during training')
    parser.add_argument('--anneal_shift', default=0., type=float, help='Annealing offset in epochs of loss terms during training')
    parser.add_argument('--anneal_max', default=2.0, type=float, help='Annealing maximum value')
    parser.add_argument(
        '--save_last_model', default=False, action='store_true',
        help='If true saves the model weights from the last training epoch, otherwise the model with best validation loss is saved.',
    )

    # 2D image data augmentation parameters
    parser.add_argument('--rotation_factor', default=0., type=float, help='for data augmentation, a float represented as fraction of 2 Pi, e.g., rotation_factor = 0.014 results in an output rotated by a random amount in the range [-5 degrees, 5 degrees]')
    parser.add_argument('--zoom_factor', default=0., type=float, help='for data augmentation, a float represented as fraction of value, e.g., zoom_factor = 0.05 results in an output zoomed in a random amount in the range [-5%, 5%]')
    parser.add_argument('--translation_factor', default=0., type=float, help='for data augmentation, a float represented as a fraction of value, e.g., translation_factor = 0.05 results in an output shifted by a random amount in the range [-5%, 5%] in the x- and y- directions')

    # Run specific and debugging arguments
    parser.add_argument('--id', default='no_id', help='Identifier for this run, user-defined string to keep experiments organized.')
    parser.add_argument('--random_seed', default=12878, type=int, help='Random seed to use throughout run.  Always use np.random.')
    parser.add_argument('--write_pngs', default=False, action='store_true', help='Write pngs of slices.')
    parser.add_argument('--dpi', default=300, type=int, help='Dots per inch of figures made in plots.py')
    parser.add_argument('--plot_width', default=6, type=int, help='Width in inches of figures made in plots.py')
    parser.add_argument('--plot_height', default=6, type=int, help='Height in inches of figures made in plots.py')
    parser.add_argument('--debug', default=False, action='store_true', help='Run in debug mode.')
    parser.add_argument('--eager', default=False, action='store_true', help='Run tensorflow functions in eager execution mode (helpful for debugging).')
    parser.add_argument('--inspect_model', default=False, action='store_true', help='Plot model architecture, measure inference and training speeds.')
    parser.add_argument('--inspect_show_labels', default=True, action='store_true', help='Plot model architecture with labels for each layer.')
    parser.add_argument('--alpha', default=0.5, type=float, help='Alpha transparency for t-SNE plots must in [0.0-1.0].')
    parser.add_argument('--plot_mode', default='clinical', choices=['clinical', 'full'], help='ECG view to plot for mgb ECGs.')
    parser.add_argument("--embed_visualization", help="Method to visualize embed layer. Options: None, tsne, or umap")
    parser.add_argument('--attractor_iterations', default=3, type=int, help='Number of iterations for autoencoder generated fixed points.')
    parser.add_argument("--explore_export_errors", default=False, action="store_true", help="Export error_type columns in tensors_all*.csv generated by explore.")
    parser.add_argument('--plot_hist', default=True, help='Plot histograms of continuous tensors in explore mode.')

    # Training optimization options
    parser.add_argument('--num_workers', default=multiprocessing.cpu_count(), type=int, help="Number of workers to use for every tensor generator.")
    parser.add_argument('--cache_size', default=3.5e9/multiprocessing.cpu_count(), type=float, help="Tensor map cache size per worker.")

    # Cross reference arguments
    parser.add_argument(
        '--tensors_source',
        help='Either a csv or directory of hd5 containing a source dataset.',
    )
    parser.add_argument(
        '--tensors_name', default='Tensors',
        help='Name of dataset at tensors, e.g. ECG. '
             'Adds contextual detail to summary CSV and plots.',
    )
    parser.add_argument(
        '--join_tensors', default=['partners_ecg_patientid_clean'], nargs='+',
        help='TensorMap or column name in csv of value in tensors used in join with reference. '
             'Can be more than 1 join value.',
    )
    parser.add_argument(
        '--time_tensor', default='partners_ecg_datetime',
        help='TensorMap or column name in csv of value in tensors to perform time cross-ref on. '
             'Time cross referencing is optional.',
    )
    parser.add_argument(
        '--reference_tensors',
        help='Either a csv or directory of hd5 containing a reference dataset.',
    )
    parser.add_argument(
        '--reference_name', default='Reference',
        help='Name of dataset at reference, e.g. STS. '
             'Adds contextual detail to summary CSV and plots.',
    )
    parser.add_argument(
        '--reference_join_tensors', nargs='+',
        help='TensorMap or column name in csv of value in reference used in join in tensors. '
             'Can be more than 1 join value.',
    )
    parser.add_argument(
        '--reference_start_time_tensor', action='append', nargs='+',
        help='TensorMap or column name in csv of start of time window in reference. '
             'Define multiple time windows by using this argument more than once. '
             'The number of time windows must match across all time window arguments. '
             'An integer can be provided as a second argument to specify an offset to the start time. '
             'e.g. tStart -30',
    )
    parser.add_argument(
        '--reference_end_time_tensor', action='append', nargs='+',
        help='TensorMap or column name in csv of end of time window in reference. '
             'Define multiple time windows by using this argument more than once. '
             'The number of time windows must match across all time window arguments. '
             'An integer can be provided as a second argument to specify an offset to the end time. '
             'e.g. tEnd 30',
    )
    parser.add_argument(
        '--window_name', action='append',
        help='Name of time window. By default, the name of the window is the index of the window. '
             'Define multiple time windows by using this argument more than once. '
             'The number of time windows must match across all time window arguments.',
    )
    parser.add_argument(
        '--order_in_window', action='append', choices=['newest', 'oldest', 'random'],
        help='If specified, exactly --number_in_window rows with join tensor are used in time window. '
             'Defines which source tensors in a time series to use in time window. '
             'Define multiple time windows by using this argument more than once. '
             'The number of time windows must match across all time window arguments.',
    )
    parser.add_argument(
        '--number_per_window', type=int, default=1,
        help='Minimum number of rows with join tensor to use in each time window. '
             'By default, 1 tensor is used for each window.',
    )
    parser.add_argument(
        '--match_any_window', action='store_true', default=False,
        help='If specified, join tensor does not need to be found in every time window. '
             'Join tensor needs only be found in at least 1 time window. '
             'Default only use rows with join tensor that appears across all time windows.',
    )
    parser.add_argument(
        '--reference_labels', nargs='+',
        help='TensorMap or column name of values in csv to report distribution on, e.g. mortality. '
             'Label distribution reporting is optional. Can list multiple labels to report.',
    )
    parser.add_argument(
        '--time_frequency',
        help='Frequency string indicating resolution of counts over time. Also multiples are accepted, e.g. "3M".',
        default='3M',
    )

    # Arguments for explorations/infer_stats_from_segmented_regions
    parser.add_argument('--analyze_ground_truth', default=False, action='store_true', help='Whether or not to filter by images with ground truth segmentations, for comparison')
    parser.add_argument('--structures_to_analyze', nargs='*', default=[], help='Structure names to include in the .tsv files and scatter plots. Must be in the same order as the output channel map. Use + to merge structures before postprocessing, and ++ to merge structures after postprocessing. E.g., --structures_to_analyze interventricular_septum LV_free_wall anterolateral_pap posteromedial_pap interventricular_septum+LV_free_wall anterolateral_pap++posteromedial_pap')
    parser.add_argument('--erosion_radius', nargs='*', default=[], type=int, help='Radius of the unit disk structuring element for erosion preprocessing, optionally as a list per structure to analyze')
    parser.add_argument('--intensity_thresh', type=float, help='Threshold value for preprocessing')
    parser.add_argument('--intensity_thresh_in_structures', nargs='*', default=[], help='Structure names whose pixels should be replaced if the images has intensity above the threshold')
    parser.add_argument('--intensity_thresh_out_structure', help='Replacement structure name')
    parser.add_argument('--intensity_thresh_auto', default=None, type=str, help='Preprocessing using histograms or k-means into two clusters, using the image or a region')
    parser.add_argument('--intensity_thresh_auto_region_radius', default=5, type=int, help='Radius of the unit disk structuring element for auto-thresholidng in a region')
    parser.add_argument('--intensity_thresh_auto_clip_low', default=0.65, type=float, help='Lower clip value before auto thresholding')
    parser.add_argument('--intensity_thresh_auto_clip_high', default=2, type=float, help='Higher clip value before auto thresholding')


    # TensorMap prefix for convenience
    parser.add_argument('--tensormap_prefix', default="ml4h.tensormap", type=str, help="Module prefix path for TensorMaps. Defaults to \"ml4h.tensormap\"")

    #Parent Sort enable or disable
    parser.add_argument('--parent_sort', default=True, type=lambda x: x.lower() == 'true', help='disable or enable parent_sort on output tmaps')
    #Dictionary outputs
    parser.add_argument('--named_outputs', default=False, type=lambda x: x.lower() == 'true', help='pass output tmaps as dictionaries if true else pass as list')
    args = parser.parse_args()
    _process_args(args)
    return args


def tensormap_lookup(module_string: str, prefix: str = "ml4h.tensormap"):
    tm = make_mgb_dynamic_tensor_maps(module_string)
    if isinstance(tm, TensorMap) == True:
        return tm

    tm = make_test_tensor_maps(module_string)
    if isinstance(tm, TensorMap) == True:
        return tm

    if isinstance(module_string, str) == False:
        raise TypeError(f"Input name must be a string. Given: {type(module_string)}")
    if len(module_string) == 0:
        raise ValueError(f"Input name cannot be empty.")
    path_string = module_string
    if prefix:
        if isinstance(prefix, str) == False:
            raise TypeError(f"Prefix must be a string. Given: {type(prefix)}")
        if len(prefix) == 0:
            raise ValueError(f"Prefix cannot be set to an emtpy string.")
        path_string = '.'.join([prefix, module_string])
    else:
        if '.'.join(path_string.split('.')[0:2]) != 'ml4h.tensormap':
            raise ValueError(f"TensorMaps must reside in the path 'ml4h.tensormap.*'. Given: {module_string}")

    try:
        i = importlib.import_module('.'.join(path_string.split('.')[:-1]))
    except ModuleNotFoundError:
        raise ModuleNotFoundError(f"Could not resolve library {'.'.join(path_string.split('.')[:-1])} for target tensormap {module_string}")
    try:
        tm = getattr(i, path_string.split('.')[-1])
    except AttributeError:
        logging.warning(f"Module {'.'.join(path_string.split('.')[:-1])} has no TensorMap called {path_string.split('.')[-1]}")
        return None
        #raise AttributeError(f"Module {'.'.join(path_string.split('.')[:-1])} has no TensorMap called {path_string.split('.')[-1]}")

    if isinstance(tm, TensorMap) == False:
        raise TypeError(f"Target value is not a TensorMap object. Returned: {type(tm)}")

    return tm


def _process_u_connect_args(u_connect: Optional[List[List]], tensormap_prefix) -> Dict[TensorMap, Set[TensorMap]]:
    u_connect = u_connect or []
    new_u_connect = defaultdict(set)
    for connect_pair in u_connect:
        tmap_key_in, tmap_key_out = connect_pair[0], connect_pair[1]
        tmap_in, tmap_out = tensormap_lookup(tmap_key_in, tensormap_prefix), tensormap_lookup(tmap_key_out, tensormap_prefix)
        if tmap_in.shape[:-1] != tmap_out.shape[:-1]:
            raise TypeError(f'u_connect of {tmap_in} {tmap_out} requires matching shapes besides channel dimension.')
        if tmap_in.axes() < 2 or tmap_out.axes() < 2:
            raise TypeError(f'Cannot u_connect 1d TensorMaps ({tmap_in} {tmap_out}).')
        new_u_connect[tmap_in].add(tmap_out)
    return new_u_connect


def _process_pair_args(pairs: Optional[List[List]], tensormap_prefix) -> List[Tuple[TensorMap, TensorMap]]:
    pairs = pairs or []
    new_pairs = []
    for pair in pairs:
        new_pairs.append((tensormap_lookup(pair[0], tensormap_prefix), tensormap_lookup(pair[1], tensormap_prefix)))
    return new_pairs


def generate_tensormap_id(tm):
    return hashlib.sha256(str(tm).encode("utf-8")).hexdigest()


def generate_model_id(model_name: str, tensor_maps_in: List[TensorMap], tensor_maps_out: List[TensorMap]):
    str_i = '_'.join([str(tmi) for tmi in tensor_maps_in])
    str_o = '_'.join([str(tmo) for tmo in tensor_maps_out])
    model_str = f'{str_i}&{str_o}'
    return hashlib.sha256(model_str.encode("utf-8")).hexdigest()


def _process_args(args):
    now_string = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
    args_file = os.path.join(args.output_folder, args.id, 'arguments_' + now_string + '.txt')
    command_line = f"\n./scripts/tf.sh {' '.join(sys.argv)}\n"
    if not os.path.exists(os.path.dirname(args_file)):
        os.makedirs(os.path.dirname(args_file))
    with open(args_file, 'w') as f:
        f.write(command_line)
        for k, v in sorted(args.__dict__.items(), key=operator.itemgetter(0)):
            f.write(k + ' = ' + str(v) + '\n')
    load_config(args.logging_level, os.path.join(args.output_folder, args.id), 'log_' + now_string, args.min_sample_id)
    args.u_connect = _process_u_connect_args(args.u_connect, args.tensormap_prefix)
    args.pairs = _process_pair_args(args.pairs, args.tensormap_prefix)

    args.tensor_maps_in = []
    args.tensor_maps_out = []
    if args.text_file is not None or args.hd5_as_text is not None:
        del args.input_tensors[0]
        del args.output_tensors[0]
        if args.hd5_as_text is not None:
            window_shape = (int(np.sqrt(args.text_window)), int(np.sqrt(args.text_window)))
            input_map, output_map = generate_random_pixel_as_text_tensor_maps(args.tensors, args.hd5_as_text, window_shape)
        else:
            input_map, output_map = generate_random_text_tensor_maps(args.text_file, args.text_window)
        args.tensor_maps_in.append(input_map)
        args.tensor_maps_out.append(output_map)

    if args.latent_input_file is not None:
        args.tensor_maps_in.append(
            generate_latent_tensor_map_from_file(args.latent_input_file, args.input_tensors.pop(0))
        )
    args.tensor_maps_in.extend([tensormap_lookup(it, args.tensormap_prefix) for it in args.input_tensors])

    if args.continuous_file is not None:
        # Continuous TensorMap(s) generated from file is given the name specified by the first output_tensors argument
        for column in args.continuous_file_columns:
            args.tensor_maps_out.append(
                generate_continuous_tensor_map_from_file(
                    args.continuous_file,
                    column,
                    args.output_tensors.pop(0),
                    args.continuous_file_normalize,
                    args.continuous_file_discretization_bounds,
                ),
            )
    if args.categorical_file is not None:
        # Categorical TensorMap(s) generated from file is given the name specified by the first output_tensors argument
        for column in args.categorical_file_columns:
            args.tensor_maps_out.append(
                generate_categorical_tensor_map_from_file(
                    args.categorical_file,
                    column,
                    args.output_tensors.pop(0),
                ),
            )

    if len(args.latent_output_files) > 0:
        for lof in args.latent_output_files:
            args.tensor_maps_out.append(
                generate_latent_tensor_map_from_file(lof, args.output_tensors.pop(0)),
            )

    args.tensor_maps_out.extend([tensormap_lookup(ot, args.tensormap_prefix) for ot in args.output_tensors])
    args.tensor_maps_out = parent_sort(args.tensor_maps_out)
    args.tensor_maps_protected = [tensormap_lookup(it, args.tensormap_prefix) for it in args.protected_tensors]

    check_no_bottleneck(args.u_connect, args.tensor_maps_out)

    if args.learning_rate_schedule is not None and args.patience < args.epochs:
        raise ValueError(f'learning_rate_schedule is not compatible with ReduceLROnPlateau. Set patience > epochs.')

    np.random.seed(args.random_seed)

    logging.info(f"Command Line was: {command_line}")
    logging.info(f'Input SHA256s: {[(tm.name, generate_tensormap_id(tm)) for tm in args.tensor_maps_in]}')
    logging.info(f'Output SHA256s: {[(tm.name, generate_tensormap_id(tm)) for tm in args.tensor_maps_out]}')
    logging.info(f'Model SHA256: {generate_model_id(args.id, args.tensor_maps_in, args.tensor_maps_out)}')
    logging.info(f"Arguments are {args}\n")

    if args.eager:
        import tensorflow as tf
        tf.config.experimental_run_functions_eagerly(True)


def _build_mgb_time_series_tensor_maps(
        needed_name: str,
        time_series_limit: int = 1,
) -> Dict[str, TensorMap]:
    if needed_name.endswith('_newest'):
        base_split = '_newest'
        time_series_order = TimeSeriesOrder.NEWEST
    elif needed_name.endswith('_oldest'):
        base_split = '_oldest'
        time_series_order = TimeSeriesOrder.OLDEST
    elif needed_name.endswith('_random'):
        base_split = '_random'
        time_series_order = TimeSeriesOrder.RANDOM
    else:
        return None

    base_name = needed_name.split(base_split)[0]
    time_tmap = copy.deepcopy(tensormap_lookup(base_name, prefix="ml4h.tensormap.mgb.ecg"))
    time_tmap.name = needed_name
    time_tmap.shape = time_tmap.shape[1:]
    time_tmap.time_series_limit = time_series_limit
    time_tmap.time_series_order = time_series_order
    time_tmap.metrics = None
    time_tmap.infer_metrics()

    return time_tmap
