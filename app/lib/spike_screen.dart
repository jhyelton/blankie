import 'package:audio_service/audio_service.dart';
import 'package:flutter/material.dart';

import 'download_state.dart';
import 'episode_downloader.dart';
import 'spike_audio_handler.dart';

/// Disposable screen for the audio spike (design D5). Everything shown here
/// comes from the handler's streams, so changes made from the lock screen or
/// headphones show up here too.
class SpikeScreen extends StatelessWidget {
  const SpikeScreen({
    super.key,
    required this.handler,
    required this.downloader,
  });

  final SpikeAudioHandler handler;
  final EpisodeDownloader downloader;

  @override
  Widget build(BuildContext context) {
    final episode = handler.episode;
    return Scaffold(
      appBar: AppBar(title: const Text('blankie · audio spike')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: AspectRatio(
                aspectRatio: 1,
                child: Image.network(
                  episode.artworkUrl,
                  errorBuilder: (_, _, _) =>
                      const ColoredBox(color: Colors.black12),
                ),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              episode.title,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            Text(episode.showName),
            const SizedBox(height: 16),
            _SeekBar(handler: handler),
            _Controls(handler: handler),
            const SizedBox(height: 8),
            ValueListenableBuilder(
              valueListenable: handler.source,
              builder: (_, source, _) => Text(
                'Source: ${switch (source) {
                  PlaybackSource.stream => 'stream',
                  PlaybackSource.local => 'local',
                  null => '—',
                }}',
                key: const Key('source'),
              ),
            ),
            const Divider(height: 32),
            _DownloadPanel(downloader: downloader),
          ],
        ),
      ),
    );
  }
}

class _SeekBar extends StatefulWidget {
  const _SeekBar({required this.handler});

  final SpikeAudioHandler handler;

  @override
  State<_SeekBar> createState() => _SeekBarState();
}

class _SeekBarState extends State<_SeekBar> {
  double? _dragValue;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<MediaItem?>(
      stream: widget.handler.mediaItem,
      builder: (context, itemSnap) {
        final duration = itemSnap.data?.duration ?? Duration.zero;
        return StreamBuilder<Duration>(
          stream: widget.handler.positionStream,
          builder: (context, posSnap) {
            final position = posSnap.data ?? Duration.zero;
            final max = duration.inMilliseconds.toDouble();
            final value =
                _dragValue ??
                position.inMilliseconds.toDouble().clamp(0, max <= 0 ? 0 : max);
            return Column(
              children: [
                Slider(
                  max: max <= 0 ? 1 : max,
                  value: max <= 0 ? 0 : value.toDouble(),
                  onChanged: max <= 0
                      ? null
                      : (v) => setState(() => _dragValue = v),
                  onChangeEnd: (v) {
                    widget.handler.seek(Duration(milliseconds: v.round()));
                    setState(() => _dragValue = null);
                  },
                ),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      _format(Duration(milliseconds: value.round())),
                      key: const Key('position'),
                    ),
                    Text(_format(duration)),
                  ],
                ),
              ],
            );
          },
        );
      },
    );
  }
}

class _Controls extends StatelessWidget {
  const _Controls({required this.handler});

  final SpikeAudioHandler handler;

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<PlaybackState>(
      stream: handler.playbackState,
      builder: (context, snap) {
        final state = snap.data;
        final playing = state?.playing ?? false;
        final busy =
            state?.processingState == AudioProcessingState.loading ||
            state?.processingState == AudioProcessingState.buffering;
        return Column(
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  iconSize: 40,
                  tooltip: 'Back 15 s',
                  icon: const Icon(Icons.replay),
                  onPressed: handler.rewind,
                ),
                IconButton(
                  iconSize: 64,
                  tooltip: playing ? 'Pause' : 'Play',
                  icon: Icon(
                    playing ? Icons.pause_circle : Icons.play_circle,
                  ),
                  onPressed: playing ? handler.pause : handler.play,
                ),
                IconButton(
                  iconSize: 40,
                  tooltip: 'Forward 30 s',
                  icon: const Icon(Icons.forward_30),
                  onPressed: handler.fastForward,
                ),
              ],
            ),
            Text(
              '${state?.processingState.name ?? 'idle'}'
              '${busy ? '…' : ''}',
            ),
          ],
        );
      },
    );
  }
}

class _DownloadPanel extends StatelessWidget {
  const _DownloadPanel({required this.downloader});

  final EpisodeDownloader downloader;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<DownloadState>(
      valueListenable: downloader.state,
      builder: (context, state, _) {
        final downloading = state.phase == DownloadPhase.downloading;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(state.describe(), key: const Key('download')),
            if (downloading) ...[
              const SizedBox(height: 8),
              LinearProgressIndicator(value: state.fraction),
            ],
            const SizedBox(height: 8),
            switch (state.phase) {
              DownloadPhase.notDownloaded => FilledButton.icon(
                icon: const Icon(Icons.download),
                label: const Text('Download'),
                onPressed: downloader.download,
              ),
              DownloadPhase.failed => FilledButton.icon(
                icon: const Icon(Icons.refresh),
                label: const Text('Retry download'),
                onPressed: downloader.retry,
              ),
              DownloadPhase.downloading ||
              DownloadPhase.downloaded => const SizedBox.shrink(),
            },
          ],
        );
      },
    );
  }
}

String _format(Duration d) {
  final h = d.inHours;
  final m = d.inMinutes.remainder(60).toString().padLeft(2, '0');
  final s = d.inSeconds.remainder(60).toString().padLeft(2, '0');
  return '$h:$m:$s';
}
