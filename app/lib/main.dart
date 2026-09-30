import 'package:audio_service/audio_service.dart';
import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'download_state.dart';
import 'episode.dart';
import 'episode_downloader.dart';
import 'position_store.dart';
import 'spike_audio_handler.dart';
import 'spike_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final downloader = EpisodeDownloader(taxiDriver);
  await downloader.init();

  final handler = await AudioService.init(
    builder: () => SpikeAudioHandler(
      taxiDriver,
      SharedPreferencesPositionStore(SharedPreferencesAsync()),
    ),
    config: const AudioServiceConfig(
      // Android isn't set up in this change; these are required fields.
      androidNotificationChannelId: 'com.jhyelton.blankie.playback',
      androidNotificationChannelName: 'Playback',
      fastForwardInterval: Duration(seconds: 30),
      rewindInterval: Duration(seconds: 15),
    ),
  );
  await handler.init(localPath: downloader.localPath);

  // When a download finishes, switch the player over to the local file.
  downloader.state.addListener(() {
    final path = downloader.localPath;
    if (downloader.state.value.phase == DownloadPhase.downloaded &&
        path != null) {
      handler.useLocalFile(path);
    }
  });

  runApp(
    MaterialApp(
      title: 'blankie',
      theme: ThemeData(colorSchemeSeed: Colors.deepOrange),
      home: SpikeScreen(handler: handler, downloader: downloader),
    ),
  );
}
