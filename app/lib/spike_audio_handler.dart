import 'dart:async';

import 'package:audio_service/audio_service.dart';
import 'package:audio_session/audio_session.dart';
import 'package:flutter/widgets.dart';
import 'package:just_audio/just_audio.dart';

import 'episode.dart';
import 'position_store.dart';

enum PlaybackSource { stream, local }

/// Connects a `just_audio` player to the OS media session through
/// `audio_service` (design D2).
///
/// `audio_service` publishes the [MediaItem] and [PlaybackState] to the lock
/// screen and Control Center, and routes remote commands (lock screen,
/// headphones, car) back here. The skip intervals come from
/// `AudioServiceConfig`: iOS shows them on the lock-screen skip buttons, which
/// call [fastForward] and [rewind] from [SeekHandler].
class SpikeAudioHandler extends BaseAudioHandler with SeekHandler {
  SpikeAudioHandler(this.episode, this._positions);

  static const saveInterval = Duration(seconds: 10);

  final Episode episode;
  final PositionStore _positions;

  // handleInterruptions (the default) makes just_audio pause when another
  // audio source interrupts, resume if iOS says `shouldResume` when it ends,
  // and pause when the output route goes away (headphones unplugged). It
  // relies on the audio session configured in [init].
  final _player = AudioPlayer(handleInterruptions: true);

  final source = ValueNotifier<PlaybackSource?>(null);

  Timer? _saveTimer;
  AppLifecycleListener? _lifecycle;
  DateTime? _lastRecovery;

  Future<void> init({String? localPath}) async {
    // `speech` = playback category + spoken-audio mode: plays with the silent
    // switch on and in the background, and other apps' prompts pause us
    // instead of ducking.
    final session = await AudioSession.instance;
    await session.configure(const AudioSessionConfiguration.speech());

    mediaItem.add(
      MediaItem(
        id: episode.guid,
        title: episode.title,
        artist: episode.showName,
        album: episode.showName,
        artUri: Uri.parse(episode.artworkUrl),
        duration: episode.duration,
      ),
    );

    _player.playbackEventStream.listen(
      (_) => _broadcastState(),
      onError: (Object e, StackTrace st) => debugPrint('Playback error: $e'),
    );
    _player.playingStream.listen(_onPlayingChanged);
    _player.durationStream.listen((d) {
      final item = mediaItem.value;
      if (d != null && item != null && item.duration != d) {
        mediaItem.add(item.copyWith(duration: d));
      }
    });
    _player.errorStream.listen(_onError);

    // Covers backgrounding and the app being torn down. A force-quit from the
    // app switcher gets no callback, so the 10 s timer bounds what's lost.
    _lifecycle = AppLifecycleListener(
      onStateChange: (state) {
        if (state == AppLifecycleState.paused ||
            state == AppLifecycleState.detached) {
          unawaited(savePosition());
        }
      },
    );

    final saved = await _positions.load(episode.guid) ?? Duration.zero;
    try {
      await _load(localPath: localPath, position: saved);
    } on PlayerException catch (e) {
      // For example, streaming while offline. The screen still opens.
      debugPrint('Initial load failed ${e.code}: ${e.message}');
    }
  }

  Future<void> _load({String? localPath, required Duration position}) async {
    final audioSource = localPath != null
        ? AudioSource.file(localPath)
        : AudioSource.uri(Uri.parse(episode.enclosureUrl));
    source.value = localPath != null
        ? PlaybackSource.local
        : PlaybackSource.stream;
    await _player.setAudioSource(audioSource, initialPosition: position);
  }

  /// Switches to the downloaded file, keeping position and play state.
  Future<void> useLocalFile(String path) async {
    if (source.value == PlaybackSource.local) return;
    final wasPlaying = _player.playing;
    await _load(localPath: path, position: _player.position);
    if (wasPlaying) unawaited(_player.play());
  }

  Future<void> savePosition() =>
      _positions.save(episode.guid, _player.position);

  void _onPlayingChanged(bool playing) {
    _saveTimer?.cancel();
    if (playing) {
      _saveTimer = Timer.periodic(saveInterval, (_) => savePosition());
    } else {
      // Any pause, whatever caused it: the app, the lock screen, headphones,
      // or an interruption.
      unawaited(savePosition());
    }
  }

  // The signed CDN URL behind the enclosure expires. If the stream fails (for
  // example on a seek after a long pause), reload from the original URL at the
  // last position. Rate-limited so a real outage doesn't loop.
  Future<void> _onError(PlayerException e) async {
    debugPrint('Player error ${e.code}: ${e.message}');
    if (source.value != PlaybackSource.stream) return;
    final now = DateTime.now();
    if (_lastRecovery != null &&
        now.difference(_lastRecovery!) < const Duration(seconds: 30)) {
      return;
    }
    _lastRecovery = now;
    final position = _player.position;
    final wasPlaying = _player.playing;
    try {
      await _load(position: position);
      if (wasPlaying) unawaited(_player.play());
    } on PlayerException catch (e) {
      debugPrint('Stream reload failed ${e.code}: ${e.message}');
    }
  }

  @override
  Future<void> play() => _player.play();

  @override
  Future<void> pause() => _player.pause();

  @override
  Future<void> seek(Duration position) async {
    final duration = _player.duration ?? episode.duration;
    final clamped = position < Duration.zero
        ? Duration.zero
        : (position > duration ? duration : position);
    await _player.seek(clamped);
    await savePosition();
  }

  @override
  Future<void> stop() async {
    await savePosition();
    await _player.stop();
    await super.stop();
  }

  void _broadcastState() {
    playbackState.add(
      playbackState.value.copyWith(
        controls: [
          MediaControl.rewind,
          if (_player.playing) MediaControl.pause else MediaControl.play,
          MediaControl.fastForward,
        ],
        systemActions: const {MediaAction.seek},
        androidCompactActionIndices: const [0, 1, 2],
        processingState: const {
          ProcessingState.idle: AudioProcessingState.idle,
          ProcessingState.loading: AudioProcessingState.loading,
          ProcessingState.buffering: AudioProcessingState.buffering,
          ProcessingState.ready: AudioProcessingState.ready,
          ProcessingState.completed: AudioProcessingState.completed,
        }[_player.processingState]!,
        playing: _player.playing,
        updatePosition: _player.position,
        bufferedPosition: _player.bufferedPosition,
        speed: _player.speed,
      ),
    );
  }

  /// The player's position, for the spike screen's seek bar.
  Stream<Duration> get positionStream => _player.positionStream;

  Future<void> dispose() async {
    _saveTimer?.cancel();
    _lifecycle?.dispose();
    await _player.dispose();
    source.dispose();
  }
}
