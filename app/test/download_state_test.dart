import 'package:blankie/download_state.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const size = 225419199; // Server Content-Length of the spike episode.

  group('transitions', () {
    test('starts not downloaded and not playable', () {
      const state = DownloadState.notDownloaded();
      expect(state.phase, DownloadPhase.notDownloaded);
      expect(state.isPlayable, isFalse);
    });

    test('not downloaded -> downloading -> downloaded', () {
      var state = const DownloadState.notDownloaded().started();
      expect(state.phase, DownloadPhase.downloading);
      expect(state.isPlayable, isFalse);

      state = state.progressed(progress: 0.5, expectedFileSize: size);
      expect(state.phase, DownloadPhase.downloading);
      expect(state.isPlayable, isFalse);

      state = state.completed();
      expect(state.phase, DownloadPhase.downloaded);
      expect(state.isPlayable, isTrue);
      expect(state.fraction, 1);
    });

    test('downloading -> failed keeps a partial download unplayable', () {
      final state = const DownloadState.notDownloaded()
          .started()
          .progressed(progress: 0.99, expectedFileSize: size)
          .failed('network lost');
      expect(state.phase, DownloadPhase.failed);
      expect(state.isPlayable, isFalse);
      expect(state.error, 'network lost');
    });

    test('failed -> retry starts again from zero', () {
      final state = const DownloadState.notDownloaded()
          .started()
          .progressed(progress: 0.4, expectedFileSize: size)
          .failed('network lost')
          .started();
      expect(state.phase, DownloadPhase.downloading);
      expect(state.bytesReceived, 0);
      expect(state.isPlayable, isFalse);
    });

    test('progress is ignored unless downloading', () {
      const state = DownloadState.notDownloaded();
      expect(
        state.progressed(progress: 0.5, expectedFileSize: size),
        same(state),
      );
    });

    test('negative progress values (plugin status markers) are ignored', () {
      final state = const DownloadState.notDownloaded().started();
      expect(
        state.progressed(progress: -1, expectedFileSize: size),
        same(state),
      );
    });
  });

  group('progress', () {
    test('uses the server-reported size, not the feed length of 0', () {
      final state = const DownloadState.notDownloaded().started().progressed(
        progress: 0.25,
        expectedFileSize: size,
      );
      expect(state.totalBytes, size);
      expect(state.fraction, closeTo(0.25, 1e-6));
      expect(state.describe(), startsWith('Downloading 25.0%'));
    });

    test('reaches 100% at the end of the transfer', () {
      final state = const DownloadState.notDownloaded().started().progressed(
        progress: 1,
        expectedFileSize: size,
      );
      expect(state.fraction, 1);
    });

    test('is indeterminate when the size is unknown', () {
      for (final size in [-1, 0]) {
        final state = const DownloadState.notDownloaded().started().progressed(
          progress: 0.1,
          expectedFileSize: size,
        );
        // A null fraction renders LinearProgressIndicator as indeterminate.
        expect(state.fraction, isNull, reason: 'size $size');
        expect(state.describe(), 'Downloading (size unknown)');
      }
    });
  });

  group('reconcile at startup', () {
    test('a renamed final file is downloaded, whatever the record says', () {
      for (final last in LastTaskStatus.values) {
        final state = DownloadState.reconcile(
          finalFileExists: true,
          tempFileExists: false,
          lastStatus: last,
        );
        expect(state.isPlayable, isTrue, reason: '$last');
      }
    });

    test('a temp file alone is never playable', () {
      for (final last in LastTaskStatus.values) {
        final state = DownloadState.reconcile(
          finalFileExists: false,
          tempFileExists: true,
          lastStatus: last,
        );
        expect(state.isPlayable, isFalse, reason: '$last');
      }
    });

    test('completed in the background still needs the rename', () {
      final state = DownloadState.reconcile(
        finalFileExists: false,
        tempFileExists: true,
        lastStatus: LastTaskStatus.complete,
      );
      expect(state.phase, DownloadPhase.downloading);
    });

    test('an active task is still downloading', () {
      final state = DownloadState.reconcile(
        finalFileExists: false,
        tempFileExists: false,
        lastStatus: LastTaskStatus.active,
      );
      expect(state.phase, DownloadPhase.downloading);
    });

    test('a failed task offers a retry', () {
      final state = DownloadState.reconcile(
        finalFileExists: false,
        tempFileExists: false,
        lastStatus: LastTaskStatus.failed,
      );
      expect(state.phase, DownloadPhase.failed);
    });

    test('nothing on disk and no record is not downloaded', () {
      final state = DownloadState.reconcile(
        finalFileExists: false,
        tempFileExists: false,
        lastStatus: LastTaskStatus.none,
      );
      expect(state.phase, DownloadPhase.notDownloaded);
    });
  });
}
