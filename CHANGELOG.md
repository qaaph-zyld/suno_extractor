# Suno Library Changelog

## 2026-06-18 - Fix Liked Song Count & Resume Lyrics Extraction

### Summary
Restored verified liked song flags from May checkpoint, fixed extractor navigation, optimized metadata extraction speed.

### Changes Made
- **FIXED**: `suno_incremental_extractor.py` now navigates to `suno.com/playlist/liked` directly
- **FIXED**: Simplified song capture to find all `/song/` links regardless of parent structure
- **RESTORED**: 8,186 verified liked songs from checkpoint `suno_liked_phase2_details_2100_20260526_001659.json`
- **OPTIMIZED**: `fill_missing_metadata.py` reduced page load wait (5s→2s), lyrics wait (3s→1s), progress save batching (every song→every 10 songs)

### Current Status
- Liked songs in DB: **8,186**
- Songs with lyrics: **2,149**
- Missing lyrics: **6,037**
- Extraction speed: **~400 songs/hour**
- Estimated completion: **~15 hours**

### Files Modified
- `suno_incremental_extractor.py`
- `fill_missing_metadata.py`

### Next Steps
- Monitor extraction progress overnight
- Verify lyrics count increases
- Commit final results

---

## 2026-06-18 - Discovered Suno API & Corrected Liked Count

### Summary
Found Suno's internal API (`studio-api-prod.suno.com/api/feed/v3`), extracted true liked songs with proper `is_liked` filtering.

### Changes Made
- **DISCOVERED**: Suno API endpoint `studio-api-prod.suno.com/api/feed/v3`
- **CORRECTED**: True liked song count is **3,254** (not 8,186 from stale checkpoint)
- **ADDED**: `extract_true_liked.py` - extracts only songs with `is_liked=True` from API
- **RESET**: All `is_liked` flags to 0, then set correctly for 3,254 songs
- **REMOVED**: Old stale checkpoint data (8,186 incorrect liked songs)

### Current Status
- Liked songs in DB: **3,254**
- Songs with lyrics: ~890
- Missing lyrics: **2,364**
- Missing description: **2,436**
- Extraction speed: **~400 songs/hour**
- Estimated completion: **~6 hours**

### Files Added
- `extract_true_liked.py`
- `extract_liked_fast.py`
- `extract_liked_robust.py`

### Next Steps
- Run metadata extraction for 2,364 remaining liked songs
- Monitor progress
