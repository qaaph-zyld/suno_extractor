with open("suno_download_wav.log", "r", encoding="utf-8") as f:
    lines = f.readlines()
    for line in lines[-20:]:
        print(line.rstrip())
