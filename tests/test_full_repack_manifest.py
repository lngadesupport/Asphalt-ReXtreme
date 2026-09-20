from pathlib import Path
import xml.etree.ElementTree as ET

from tools.build_full_repack import rewrite_manifest


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def test_rewrite_manifest_sets_rextreme_identity_and_removes_online_caps(tmp_path: Path):
    manifest = tmp_path / "AppxManifest.xml"
    manifest.write_text(
        """<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
         xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10">
  <Identity Name="A278AB0D.AsphaltXtreme"
            Publisher="CN=Original"
            Version="1.7.3.8"
            ProcessorArchitecture="x86" />
  <Properties>
    <DisplayName>Asphalt Xtreme</DisplayName>
    <PublisherDisplayName>Original</PublisherDisplayName>
    <Description>Original description</Description>
  </Properties>
  <Applications>
    <Application Id="App" Executable="AMS.exe" EntryPoint="AsphaltXtreme.App">
      <uap:VisualElements DisplayName="Asphalt Xtreme" Description="Original" />
    </Application>
  </Applications>
  <Capabilities>
    <Capability Name="internetClient" />
    <Capability Name="privateNetworkClientServer" />
    <DeviceCapability Name="microphone" />
  </Capabilities>
</Package>
""",
        encoding="utf-8",
    )

    result = rewrite_manifest(manifest)

    root = ET.parse(manifest).getroot()
    identity = next(x for x in root.iter() if _local(x.tag) == "Identity")

    assert identity.attrib["Name"] == "ReXtreme.AsphaltXtreme"
    assert identity.attrib["Publisher"] == "CN=ReXtreme"
    assert identity.attrib["Version"] == "1.0.0.0"
    assert identity.attrib["ProcessorArchitecture"] == "x86"

    capabilities = [
        x.attrib.get("Name")
        for x in root.iter()
        if _local(x.tag) in {"Capability", "DeviceCapability"}
    ]
    assert "internetClient" not in capabilities
    assert "privateNetworkClientServer" not in capabilities
    assert "microphone" in capabilities

    display_names = [
        (x.text or "")
        for x in root.iter()
        if _local(x.tag) == "DisplayName"
    ]
    assert "Asphalt ReXtreme" in display_names

    assert result["old_identity"]["Name"] == "A278AB0D.AsphaltXtreme"
    assert set(result["removed_capabilities"]) == {
        "internetClient",
        "privateNetworkClientServer",
    }
