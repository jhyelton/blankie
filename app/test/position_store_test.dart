import 'package:blankie/position_store.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_platform_interface/in_memory_shared_preferences_async.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_async_platform_interface.dart';

void main() {
  late PositionStore store;

  setUp(() {
    SharedPreferencesAsyncPlatform.instance =
        InMemorySharedPreferencesAsync.empty();
    store = SharedPreferencesPositionStore(SharedPreferencesAsync());
  });

  test('missing key loads as null', () async {
    expect(await store.load('never-saved'), isNull);
  });

  test('saves and loads a position', () async {
    const position = Duration(hours: 1, minutes: 12, seconds: 30);
    await store.save('guid-a', position);
    expect(await store.load('guid-a'), position);
  });

  test('a later save overwrites an earlier one', () async {
    await store.save('guid-a', const Duration(seconds: 10));
    await store.save('guid-a', const Duration(seconds: 99));
    expect(await store.load('guid-a'), const Duration(seconds: 99));
  });

  test('positions are kept per episode', () async {
    await store.save('guid-a', const Duration(seconds: 10));
    await store.save('guid-b', const Duration(seconds: 20));
    expect(await store.load('guid-a'), const Duration(seconds: 10));
    expect(await store.load('guid-b'), const Duration(seconds: 20));
  });

  test('keeps millisecond precision', () async {
    const position = Duration(milliseconds: 13987654);
    await store.save('guid-a', position);
    expect(await store.load('guid-a'), position);
  });
}
