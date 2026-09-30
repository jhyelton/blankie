import 'package:shared_preferences/shared_preferences.dart';

/// Saves and loads the playback position of an episode.
///
/// The spike keys positions by feed GUID (design D4). blankie-v1 will swap in
/// its real database, keyed by wiki identity, behind this same interface.
abstract interface class PositionStore {
  /// Returns the saved position for [episodeId], or null if none was saved.
  Future<Duration?> load(String episodeId);

  Future<void> save(String episodeId, Duration position);
}

class SharedPreferencesPositionStore implements PositionStore {
  SharedPreferencesPositionStore(this._prefs);

  final SharedPreferencesAsync _prefs;

  static String _key(String episodeId) => 'position.$episodeId';

  @override
  Future<Duration?> load(String episodeId) async {
    final ms = await _prefs.getInt(_key(episodeId));
    return ms == null ? null : Duration(milliseconds: ms);
  }

  @override
  Future<void> save(String episodeId, Duration position) =>
      _prefs.setInt(_key(episodeId), position.inMilliseconds);
}
