from keras import backend as K
from keras.callbacks import ModelCheckpoint, LearningRateScheduler
from keras.callbacks import TensorBoard
from callbacks import ConfusionMatrixCallback
from model import speech_model, prepare_model_settings
from input_data import AudioProcessor, prepare_words_list
from classes import get_classes
from IPython import embed  # noqa


def data_gen(audio_processor, sess,
             batch_size=128,
             background_frequency=0.5, background_volume_range=0.2,
             foreground_frequency=0.5, foreground_volume_range=0.2,
             time_shift=(100.0 * 16000.0) / 1000,
             mode='validation'):
  offset = 0
  if mode != 'training':
    background_frequency = 0.0
    background_volume_range = 0.0
    foreground_frequency = 0.0
    foreground_volume_range = 0.0
    time_shift = 0

  while True:
    X, y = audio_processor.get_data(
        how_many=batch_size, offset=0 if mode == 'training' else offset,
        background_frequency=background_frequency,
        background_volume_range=background_volume_range,
        foreground_frequency=foreground_frequency,
        foreground_volume_range=foreground_volume_range,
        time_shift=time_shift, mode=mode, sess=sess)
    offset += batch_size
    if offset > ap.set_size(mode) - batch_size:
      offset = 0
    yield X, y


def lr_schedule(ep):
  # base_lr = 0.001
  base_lr = 0.001
  if ep <= 20:
    return base_lr
  elif 20 < ep <= 30:
    return base_lr / 5
  else:
    return base_lr / 10


# running_mean: -0.8, running_std: 7.0
# mfcc running_mean: -0.67, running_std: 7.45
# background_clamp running_mean: -0.00064, running_std: 0.0774, p5: -0.074, p95: 0.0697  # noqa
# np.log(11) ~ 2.4
# np.log(12) ~ 2.5
# np.log(32) ~ 3.5
if __name__ == '__main__':
  sess = K.get_session()
  data_dirs = ['data/train/audio']
  add_pseudo = True
  if add_pseudo:
    data_dirs.append('data/pseudo/audio')
  compute_mfcc = False
  sample_rate = 16000
  batch_size = 100
  classes = get_classes(wanted_only=False)
  model_settings = prepare_model_settings(
      label_count=len(prepare_words_list(classes)), sample_rate=sample_rate,
      clip_duration_ms=1000, window_size_ms=30.0, window_stride_ms=10.0,
      dct_coefficient_count=40)
  ap = AudioProcessor(
      data_dirs=data_dirs,
      silence_percentage=15.0,
      unknown_percentage=7.0,
      wanted_words=classes,
      validation_percentage=10.0,
      testing_percentage=0.0,
      model_settings=model_settings,
      compute_mfcc=compute_mfcc)
  train_gen = data_gen(ap, sess, batch_size=batch_size, mode='training')
  val_gen = data_gen(ap, sess, batch_size=batch_size, mode='validation')
  model = speech_model(
      'conv_1d_time',
      model_settings['fingerprint_size'] if compute_mfcc else sample_rate,
      num_classes=model_settings['label_count'])
  # embed()
  model.fit_generator(
      train_gen, ap.set_size('training') // batch_size,
      epochs=40, verbose=1, callbacks=[
          LearningRateScheduler(lr_schedule),
          ConfusionMatrixCallback(
              val_gen,
              ap.set_size('validation') // batch_size,
              wanted_words=prepare_words_list(get_classes(wanted_only=True)),
              all_words=prepare_words_list(classes),
              label2int=ap.word_to_index),
          TensorBoard(log_dir='logs_017'),
          ModelCheckpoint(
              'checkpoints_017/ep-{epoch:03d}-vl-{val_loss:.4f}.hdf5')])

  eval_res = model.evaluate_generator(
      val_gen, ap.set_size('validation') // batch_size)
  print(eval_res)
