require "spec_helper"
require "addressable/uri"

# Regression spec for the display_uri bidi-control report.
# Run with IDNA_MODE=pure (the pure Ruby backend), where it fails.
RSpec.describe Addressable::URI, "#display_uri" do
  it "does not render bidi or format control characters decoded from an ACE label" do
    ace = Addressable::IDNA.to_ascii("abc‮moc")
    expect(ace).to start_with("xn--")
    shown = Addressable::URI.parse("http://#{ace}.com/").display_uri.host
    expect(shown).not_to match(/[‎‏‪-‮⁦-⁩]/)
  end
end
