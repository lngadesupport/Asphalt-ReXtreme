from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
STARTUP=(ROOT/"src-reconstructed"/"campaign-core"/"CampaignStartupService.c").read_text(
    encoding="utf-8", errors="replace"
)

FORBIDDEN=(
    "CampaignGarageUiTrace",
    "CampaignFrontendGarage",
    "CampaignServiceGarage",
    "CampaignFrontendIsOwned",
    "CampaignTutorialBuild",
)

def test_startup_has_no_garage_or_tutorial_runtime_dependency():
    for token in FORBIDDEN:
        assert token not in STARTUP, token
