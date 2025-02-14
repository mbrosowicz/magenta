# -*- coding: utf-8 -*-
'''
Created on Wed Apr 29 23:34:37 2020

@author: okeyr
'''
from note_seq import midi_io as mmm

from note_seq.protobuf import music_pb2

from magenta.models.music_vae import trained_model, configs, data, music_vae_train

import numpy

import os

import tensorflow as tf
from six.moves import urllib

# from tensorflow.contrib.training import HParams
from tensor2tensor.utils.hparam import HParams

from magenta.common import merge_hparams

CONFIG_CHECKPOINT = 'groovae_2bar_melody_tap'

#TFRECORD_PATH = 'C:\\Users\\okeyr\\Documents\\tf_records\\egmd1'
# TFRECORD_PATH = os.path.join(os.path.expanduser(
#     '~'), 'Documentos', 'UFSC', 'TCC', 'tfrecords', 'eval.tfrecord')
# TFRECORD_PATH = os.path.join(os.path.expanduser(
#     '~'), 'Documentos', 'UFSC', 'TCC', 'tfrecords', 'groove_partioned', 'eval.tfrecord')
TFRECORD_PATH = 'H:\\TCC\\tfrecords\\groove_partioned'

# MUSIC_VAE_PATH = os.path.join(os.path.expanduser(
#     '~'), 'Documentos', 'UFSC', 'TCC', 'music_vae')
MUSIC_VAE_PATH = 'H:\\TCC\\music_vae_with_groove'

# OUTPUT_PATH = os.path.join(os.path.expanduser(
#     '~'), 'Documentos', 'UFSC', 'TCC', 'other_outputs', CONFIG_CHECKPOINT)
# OUTPUT_PATH = os.path.join(os.path.expanduser(
#     '~'), 'Documentos', 'UFSC', 'TCC', 'other_outputs', 'groovae_2bar_melody_tap_with_groove')
OUTPUT_PATH = 'H:\\TCC\\music_vae_with_groove\\groovae_2bar_melody_tap_with_groove_0.001'


BATCH_SIZE = 32
LEARNING_RATE = 0.001
ENC_RNN_SIZE = [512]
DEC_RNN_SIZE = [256, 256]
Z_SIZE = 256

# Params: directory (string): parent directory where midi files are located
# Return: midi files path (list string)


def note_sequence_record_iterator(path):
    '''An iterator that reads and parses NoteSequence protos from a TFRecord file.

    Args:
      path: The path to the TFRecord file containing serialized NoteSequences.

    Yields:
      NoteSequence protos.

    Raises:
      IOError: If `path` cannot be opened for reading.
    '''
    reader = tf.compat.v1.io.tf_record_iterator(path)
    for serialized_sequence in reader:
        yield music_pb2.NoteSequence.FromString(serialized_sequence)


def get_midi_files_from_directory(directory):
    allMidiFiles = []
    for obj in os.listdir(directory):
        fullPath = os.path.join(directory, obj)
        if os.path.isdir(fullPath):
            allMidiFiles = allMidiFiles + \
                get_midi_files_from_directory(fullPath)
        else:
            if obj.endswith('.mid'):
                allMidiFiles.append(fullPath)
    return allMidiFiles

# Params: midiFiles (list string): midi files path
# Return: converted midi files to note sequences (list NoteSequence)


def get_note_sequences_from_midi_files(midiFiles):
    allNoteSequences = []
    for file in midiFiles:
        noteSeq = mmm.midi_file_to_note_sequence(file)
        allNoteSequences.append(noteSeq)
    return allNoteSequences

# Params: grooveConv (models.music_vae.data.GrooveConverter)
#         noteSeqs (list NoteSequence)
# Return: data prepared to feed model (list models.music_vae.data.ConverterTensors)


def get_converter_tensors_from_note_sequences(grooveConv, noteSeqs):
    allConverterTensors = []
    for seq in noteSeqs:
        allConverterTensors.append(grooveConv.to_tensors(seq))
    return allConverterTensors

# Params: index (int). what to return { 0:inputs | 1:outputs | 2: controls | 3:lengths }
#         tensors (list models.music_vae.data.ConverterTensors)
# Return: 3-D array ready to feed model [batch_size, seq_len, seq_depth] (numpy.array)


def get_numpy_array_from_converter_tensors(tensors, index=0):
    values = []
    for tsr, i in zip(tensors, range(len(tensors))):
        dictio = {
            0: tsr.inputs,
            1: tsr.outputs,
            2: tsr.controls,
            3: tsr.lengths
        }
        value = dictio.get(index)
        if (len(value) > 0):
            for val in value:
                values.append(val)

    returnValues = numpy.zeros(
        (len(values), len(values[0]), len(values[0][0])))
    for value, i in zip(values, range(len(values))):
        returnValues[i] = value

    return returnValues

# Params: index (int). what to return { 0:inputs | 1:outputs | 2: controls | 3:lengths }
#         tensors (list models.music_vae.data.ConverterTensors)
# Return: 3-D array ready to feed model [batch_size, seq_len, seq_depth] (numpy.array)


def get_collection_from_converter_tensors(tensors, index=0):
    values = []
    for tsr, i in zip(tensors, range(len(tensors))):
        dictio = {
            0: tsr.inputs,
            1: tsr.outputs,
            2: tsr.controls,
            3: tsr.lengths
        }
        value = dictio.get(index)
        if (len(value) > 0):
            for val in value:
                values.append(val)

    return values


def download_checkpoint(model_name: str,
                        checkpoint_name: str,
                        target_dir: str):
    '''
    Downloads a Magenta checkpoint to target directory.

    Target directory target_dir will be created if it does not already exist.

        :param model_name: magenta model name to download
        :param checkpoint_name: magenta checkpoint name to download
        :param target_dir: local directory in which to write the checkpoint
    '''
    tf.gfile.MakeDirs(target_dir)
    checkpoint_target = os.path.join(target_dir, checkpoint_name)
    if not os.path.exists(checkpoint_target):
        response = urllib.request.urlopen(
            f'https://storage.googleapis.com/magentadata/models/'
            f'{model_name}/checkpoints/{checkpoint_name}')
        data = response.read()
        local_file = open(checkpoint_target, 'wb')
        local_file.write(data)
        local_file.close()


def get_model(name: str):
    '''
    Returns the model instance from its name.

        :param name: the model name
    '''
    checkpoint = name + '.tar'
    download_checkpoint('music_vae', checkpoint, 'checkpoints')
    return trained_model.TrainedModel(
        # Removes the .lohl in some training checkpoint which shares the same config
        configs.CONFIG_MAP[name.split('.')[0] if '.' in name else name],
        # The batch size changes the number of sequences to be processed together,
        # we'll be working with maximum 6 sequences (during groove)
        batch_size=12,
        checkpoint_dir_or_path=os.path.join('checkpoints', checkpoint))


config_file = configs.CONFIG_MAP[CONFIG_CHECKPOINT]

config_update_map = {}

config_update_map['eval_examples_path'] = TFRECORD_PATH

config_update_map['hparams'] = merge_hparams(config_file.hparams,
                                             HParams(batch_size=BATCH_SIZE,
                                                     learning_rate=LEARNING_RATE,
                                                     enc_rnn_size=ENC_RNN_SIZE,
                                                     dec_rnn_size=DEC_RNN_SIZE,
                                                     z_size=Z_SIZE,
                                                     ))

config_file = configs.update_config(config_file, config_update_map)

dataset = data.get_dataset(
    config_file)

try:
    input_tensors = music_vae_train._get_input_tensors(dataset, config_file)
except tf.errors.OutOfRangeError:
    pass

#sequences = get_note_sequences_from_midi_files(get_midi_files_from_directory(os.path.abspath(os.getcwd())+'/groove/drummer1/session3'))

# inputs = get_collection_from_converter_tensors(converter_tensors)

# checkpoints_path = os.path.join(
#     MUSIC_VAE_PATH, CONFIG_CHECKPOINT, 'train')
checkpoints_path = os.path.join(
    MUSIC_VAE_PATH, 'groovae_2bar_melody_tap_with_groove_0.001', 'train')

trainedModel = trained_model.TrainedModel(
    config_file, BATCH_SIZE, checkpoints_path)

#tensors = get_converter_tensors_from_note_sequences(trainedModel._config.data_converter,sequences)

#inputs = get_collection_from_converter_tensors(tensors)

# ☺seq_len = [len(inputs[0])]*len(inputs)

iterator = note_sequence_record_iterator(TFRECORD_PATH)

sequences = list()

for i in range(30):
    if i < 20:
        next(iterator)
    else:
        sequences.append(next(iterator))

tensors = get_converter_tensors_from_note_sequences(
    trainedModel._config.data_converter, sequences)

inputs_tensors = get_collection_from_converter_tensors(tensors)

print('Inputs created')

outputs_tensors = get_collection_from_converter_tensors(tensors, 1)

outputs = trainedModel._config.data_converter.from_tensors(
    outputs_tensors)

print('Outputs created')

controls = get_collection_from_converter_tensors(tensors, 2)

print('Controls created')

length = get_collection_from_converter_tensors(tensors, 3)

print('Length created')

#latentSpace = trainedModel.encode_tensors(inputs)

# outputs = outputs[:100]

# inputs = inputs[:100]

# length = length[:100]

# controls = controls[:100]

latentSpace = trainedModel.encode_tensors(inputs_tensors,
                                          length,
                                          controls)

for inpt in inputs_tensors:
    for i in range(31):
        if inpt.size != 0 and inpt[i][3] == 1:
            inpt[i][12] = 1

inputs = trainedModel._config.data_converter.from_tensors(inputs_tensors)

print('Latent space created: ENCODE')

genOutput = trainedModel.decode(latentSpace[0], 32)

# for seq,i in zip(outputSequences, range(len(outputSequences))):
#     mmm.note_sequence_to_midi_file(sequence=seq, output_file=os.path.join(OUTPUT_PATH,'eval_try_3','expected_outputs')+'\example_'+str(i)+'.mid')

# for seq2,j in zip(outputs, range(len(outputs))):
#     mmm.note_sequence_to_midi_file(sequence=seq2, output_file=os.path.join(OUTPUT_PATH,'eval_try_3','original_outputs')+'\example_'+str(j)+'.mid')

for seq1, j in zip(sequences, range(len(sequences))):
    mmm.note_sequence_to_midi_file(sequence=seq1, output_file=os.path.join(
        OUTPUT_PATH, 'final_evaluation_3')+'\_'+str(j)+'_real_output.mid')

for seq2, j in zip(inputs, range(len(inputs))):
    mmm.note_sequence_to_midi_file(sequence=seq2, output_file=os.path.join(
        OUTPUT_PATH, 'final_evaluation_3')+'\_'+str(j)+'_model_input.mid')

for seq3, j in zip(outputs, range(len(outputs))):
    mmm.note_sequence_to_midi_file(sequence=seq3, output_file=os.path.join(
        OUTPUT_PATH, 'final_evaluation_3')+'\_'+str(j)+'_model_output.mid')

for seq4, j in zip(genOutput, range(len(genOutput))):
    mmm.note_sequence_to_midi_file(sequence=seq4, output_file=os.path.join(
        OUTPUT_PATH, 'final_evaluation_3')+'\_'+str(j)+'_generated_output.mid')
