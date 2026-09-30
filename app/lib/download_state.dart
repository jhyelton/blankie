/// Download state for one episode, kept free of plugin types so it can be
/// unit-tested. `EpisodeDownloader` maps `background_downloader` events onto it.
library;

enum DownloadPhase { notDownloaded, downloading, downloaded, failed }

/// What the downloader last recorded for a task, as far as startup
/// reconciliation needs to know.
enum LastTaskStatus { none, active, complete, failed }

class DownloadState {
  const DownloadState._(
    this.phase, {
    this.bytesReceived,
    this.totalBytes,
    this.error,
  });

  const DownloadState.notDownloaded() : this._(DownloadPhase.notDownloaded);

  const DownloadState.downloaded() : this._(DownloadPhase.downloaded);

  final DownloadPhase phase;

  /// Bytes received so far, when known.
  final int? bytesReceived;

  /// Size reported by the server's `Content-Length`, when known. The feed's
  /// enclosure length is `0`, so it's never used.
  final int? totalBytes;

  final String? error;

  /// Only a completed, renamed file is playable. A partial or failed download
  /// never is.
  bool get isPlayable => phase == DownloadPhase.downloaded;

  /// Progress from 0 to 1, or null when the server didn't report a size.
  double? get fraction {
    final total = totalBytes;
    if (phase == DownloadPhase.downloaded) return 1;
    if (total == null || total <= 0) return null;
    return ((bytesReceived ?? 0) / total).clamp(0, 1).toDouble();
  }

  DownloadState started() =>
      const DownloadState._(DownloadPhase.downloading, bytesReceived: 0);

  /// Applies a progress update. [progress] is 0–1 and [expectedFileSize] is the
  /// server-reported size, or a negative number when unknown.
  DownloadState progressed({
    required double progress,
    required int expectedFileSize,
  }) {
    if (phase != DownloadPhase.downloading || progress < 0) return this;
    final total = expectedFileSize > 0 ? expectedFileSize : null;
    return DownloadState._(
      DownloadPhase.downloading,
      totalBytes: total,
      bytesReceived: total == null ? null : (progress * total).round(),
    );
  }

  /// The download finished and the temporary file was renamed.
  DownloadState completed() => const DownloadState.downloaded();

  DownloadState failed(String message) => DownloadState._(
    DownloadPhase.failed,
    bytesReceived: bytesReceived,
    totalBytes: totalBytes,
    error: message,
  );

  /// Works out the state when the app starts, including after a download
  /// finished while the app was suspended or terminated.
  static DownloadState reconcile({
    required bool finalFileExists,
    required bool tempFileExists,
    required LastTaskStatus lastStatus,
  }) {
    if (finalFileExists) return const DownloadState.downloaded();
    return switch (lastStatus) {
      // Finished in the background: the caller still has to rename it.
      LastTaskStatus.complete when tempFileExists => const DownloadState._(
        DownloadPhase.downloading,
      ),
      LastTaskStatus.active => const DownloadState._(
        DownloadPhase.downloading,
      ),
      LastTaskStatus.failed => const DownloadState.notDownloaded().failed(
        'Download failed',
      ),
      _ => const DownloadState.notDownloaded(),
    };
  }

  /// Human-readable progress for the spike screen.
  String describe() {
    switch (phase) {
      case DownloadPhase.notDownloaded:
        return 'Not downloaded';
      case DownloadPhase.downloaded:
        return 'Downloaded';
      case DownloadPhase.failed:
        return 'Failed: ${error ?? 'unknown error'}';
      case DownloadPhase.downloading:
        final f = fraction;
        if (f != null) {
          return 'Downloading ${(f * 100).toStringAsFixed(1)}% '
              '(${_mb(bytesReceived ?? 0)} of ${_mb(totalBytes!)})';
        }
        // No Content-Length: background_downloader sends no progress on iOS,
        // so the screen shows an indeterminate bar.
        return 'Downloading (size unknown)';
    }
  }

  static String _mb(int bytes) =>
      '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
}
