# Tasks: Article Reader

## Partition 1: Static Reader Core

### Templates & Formatter
- [x] Create `config/templates/article_template.j2` <!-- id: 0 -->
- [x] Update `src/media_lens/presentation/html_formatter.py` to implement `generate_article_page` <!-- id: 1 -->
- [x] Update `src/media_lens/presentation/html_formatter.py` to call generation loop <!-- id: 2 -->
- [x] Update `config/templates/weekly_template.j2` to include "Reader View" links <!-- id: 3 -->

### Deployment
- [x] Update `src/media_lens/presentation/deployer.py` to recursively find and upload all HTML files <!-- id: 4 -->

### Verification
- [x] Run `python src/media_lens/runner.py run --steps format` to generate local files <!-- id: 5 -->
- [x] Verify local `staging/articles/` date-tree structure <!-- id: 6 -->
- [x] Deploy and verify live links <!-- id: 7 -->
