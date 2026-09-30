import 'dart:async';
import 'dart:io';

import 'package:background_downloader/background_downloader.dart';
import 'package:flutter/foundation.dart';

import 'download_state.dart';
import 'episode.dart';

/// Downloads one episode with `background_downloader` (design D3).
///
/// On iOS this uses a background `URLSession`, so the transfer carries on while
/// the app is suspended or the screen is locked. The file lands under a `.part`
/// name and is renamed once complete, so a partial file is never playable.
class EpisodeDownloader {
  EpisodeDownloader(this.episode);

  final Episode episode;
  final state = ValueNotifier<DownloadState>(
    const DownloadState.notDownloaded(),
  );

  final _downloader = FileDownloader();
  StreamSubscription<TaskUpdate>? _updates;
  String? _finalPath;
  Future<void>? _finishing;

  String get _taskId => 'episode-${episode.guid}';

  /// The playable local file, or null unless the download is complete.
  String? get localPath => state.value.isPlayable ? _finalPath : null;

  // Every attempt, including retries, starts from the original enclosure URL.
  // Pausing is off because iOS resume data would hold the expiring signed
  // redirect URL instead of the original one.
  DownloadTask _task() => DownloadTask(
    taskId: _taskId,
    url: episode.enclosureUrl,
    filename: '${episode.guid}.mp3.part',
    directory: 'episodes',
    baseDirectory: BaseDirectory.applicationSupport,
    updates: Updates.statusAndProgress,
    retries: 3,
    allowPause: false,
  );

  Future<void> init() async {
    final task = _task();
    final tempPath = await task.filePath();
    _finalPath = tempPath.substring(0, tempPath.length - '.part'.length);

    _updates = _downloader.updates.listen(_onUpdate);
    // Tracks tasks in the plugin's database and replays updates that arrived
    // while the app was suspended or terminated.
    await _downloader.start();

    final record = await _downloader.database.recordForId(_taskId);
    final initial = DownloadState.reconcile(
      finalFileExists: File(_finalPath!).existsSync(),
      tempFileExists: File(tempPath).existsSync(),
      lastStatus: _lastStatus(record?.status),
    );
    if (initial.phase == DownloadPhase.downloading &&
        record?.status == TaskStatus.complete) {
      await _finish(tempPath);
    } else {
      state.value = initial;
    }
  }

  Future<void> download() async {
    if (state.value.phase == DownloadPhase.downloading ||
        state.value.isPlayable) {
      return;
    }
    // Before the first await, so a second tap sees `downloading` and returns.
    state.value = state.value.started();
    _finishing = null;
    try {
      final task = _task();
      await _deleteIfExists(await task.filePath());
      if (!await _downloader.enqueue(task)) {
        state.value = state.value.failed('Could not enqueue download');
      }
    } on Exception catch (e) {
      state.value = state.value.failed('Could not start download: $e');
    }
  }

  /// Retrying is a fresh download from the original URL.
  Future<void> retry() => download();

  Future<void> _onUpdate(TaskUpdate update) async {
    if (update.task.taskId != _taskId) return;
    switch (update) {
      case TaskProgressUpdate(:final progress, :final expectedFileSize):
        state.value = state.value.progressed(
          progress: progress,
          expectedFileSize: expectedFileSize,
        );
      case TaskStatusUpdate(:final status, :final exception):
        switch (status) {
          case TaskStatus.enqueued || TaskStatus.running:
            if (state.value.phase != DownloadPhase.downloading) {
              state.value = state.value.started();
            }
          case TaskStatus.waitingToRetry:
            break;
          case TaskStatus.complete:
            await _finish(await update.task.filePath());
          case TaskStatus.failed ||
              TaskStatus.canceled ||
              TaskStatus.notFound ||
              TaskStatus.paused:
            await _deleteIfExists(await update.task.filePath());
            state.value = state.value.failed(
              exception?.description ?? status.name,
            );
        }
    }
  }

  // At startup both init() and the replayed `complete` update call this, so it
  // runs once and later callers share the same future.
  Future<void> _finish(String tempPath) =>
      _finishing ??= _renameToFinal(tempPath);

  Future<void> _renameToFinal(String tempPath) async {
    try {
      await File(tempPath).rename(_finalPath!);
      state.value = state.value.completed();
    } on FileSystemException catch (e) {
      // Already renamed (for example by a completion handled earlier).
      if (File(_finalPath!).existsSync()) {
        state.value = state.value.completed();
      } else {
        state.value = state.value.failed('Rename failed: ${e.message}');
      }
    }
  }

  static LastTaskStatus _lastStatus(TaskStatus? status) => switch (status) {
    null => LastTaskStatus.none,
    TaskStatus.enqueued ||
    TaskStatus.running ||
    TaskStatus.waitingToRetry => LastTaskStatus.active,
    TaskStatus.complete => LastTaskStatus.complete,
    _ => LastTaskStatus.failed,
  };

  static Future<void> _deleteIfExists(String path) async {
    final file = File(path);
    if (await file.exists()) await file.delete();
  }

  Future<void> dispose() async {
    await _updates?.cancel();
    state.dispose();
  }
}
