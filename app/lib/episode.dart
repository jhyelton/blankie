/// The one episode the audio spike plays (design D5).
///
/// Values are copied from the public feed, https://feeds.megaphone.fm/blank-check.
/// At 3h53m and about 225 MB it covers both the long-playback and the
/// large-download scenarios.
class Episode {
  const Episode({
    required this.guid,
    required this.title,
    required this.showName,
    required this.enclosureUrl,
    required this.artworkUrl,
    required this.duration,
  });

  final String guid;
  final String title;
  final String showName;

  /// The original `traffic.megaphone.fm` URL. It 302-redirects to a signed CDN
  /// URL that expires, so playback and downloads always start from this URL,
  /// never from a cached redirect target (design D3).
  final String enclosureUrl;
  final String artworkUrl;

  /// Duration from the feed's `itunes:duration`. The player replaces it with
  /// the decoded duration once the audio loads.
  final Duration duration;
}

const taxiDriver = Episode(
  guid: 'ca63c896-fae9-11f0-9ff5-67d1244352a1',
  title: 'Taxi Driver with Tracy Letts',
  showName: 'Blank Check with Griffin & David',
  enclosureUrl: 'https://traffic.megaphone.fm/THI1392582979.mp3',
  artworkUrl:
      'https://megaphone.imgix.net/podcasts/ca63c896-fae9-11f0-9ff5-67d1244352a1/image/8e5722474ef424b31b04cfd9c5d04277.png?ixlib=rails-4.3.1&max-w=3000&max-h=3000&fit=crop&auto=format,compress',
  duration: Duration(seconds: 13988),
);
