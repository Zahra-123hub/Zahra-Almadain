/// The measures of the design in one place: spacing, corner radii, animation times and window widths.
class Gap {
  static const double xs = 4;
  static const double s = 8;
  static const double m = 12;
  static const double l = 16;
  static const double xl = 24;
  static const double xxl = 32;
}

class Rad {
  static const double s = 10;
  static const double m = 16;
  static const double l = 24;
}

class Dur {
  static const fast = Duration(milliseconds: 150);
  static const normal = Duration(milliseconds: 250);
}

class Breakpoints {
  /// From this width on, the sidebar replaces the bottom bar.
  static const double wide = 840;

  /// The reading width of the content in a wide window.
  static const double content = 980;
}
