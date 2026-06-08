#!/usr/bin/env python3
import io, sys, sqlite3, shutil
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

SRC = Path("suno_downloads")
DST = Path("suno_library/audio")

def main():
    files = list(SRC.glob("*.*"))
    print("Moving %d files from %s to %s" % (len(files), SRC, DST))
    moved = 0
    failed = 0

    conn = sqlite3.connect("suno_library.db", timeout=30.0)
    c = conn.cursor()

    for f in files:
        dest = DST / f.name
        if dest.exists():
            print("  Skip (exists): %s" % f.name)
            continue
        try:
            shutil.move(str(f), str(dest))
            # Update DB paths
            c.execute("UPDATE songs SET local_audio_path = ? WHERE local_audio_path LIKE ?",
                      (str(dest), "%" + f.name + "%"))
            moved += 1
            print("  Moved: %s" % f.name)
        except Exception as e:
            print("  Failed: %s (%s)" % (f.name, e))
            failed += 1

    conn.commit()
    conn.close()
    print("Done: %d moved, %d failed" % (moved, failed))

if __name__ == "__main__":
    main()
