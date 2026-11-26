"""Creates the sample spreadsheet and three sample certificate backgrounds."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = HERE.parent / "editor_component" / "fonts"


def font(name, size):
    return ImageFont.truetype(str(FONT / name), size)


def border(d, w, h, color, inset=40, width=10):
    d.rectangle([inset, inset, w - inset, h - inset], outline=color, width=width)
    d.rectangle([inset + 26, inset + 26, w - inset - 26, h - inset - 26], outline=color, width=3)


def centered(d, w, y, text, f, fill):
    box = d.textbbox((0, 0), text, font=f)
    d.text(((w - (box[2] - box[0])) / 2 - box[0], y), text, font=f, fill=fill)


def classic(path):
    w, h = 2339, 1654
    img = Image.new("RGB", (w, h), (253, 250, 240))
    d = ImageDraw.Draw(img)
    border(d, w, h, (176, 128, 30), 60, 14)
    centered(d, w, 230, "CERTIFICATE", font("CinzelDecorative-Bold.ttf", 150), (27, 42, 90))
    centered(d, w, 430, "OF ACHIEVEMENT", font("Lato-Regular.ttf", 54), (120, 120, 120))
    centered(d, w, 640, "This certificate is proudly presented to", font("CrimsonText-Italic.ttf", 62), (60, 60, 60))
    d.line([(560, 900), (w - 560, 900)], fill=(60, 60, 60), width=5)           # name line
    centered(d, w, 960, "in recognition of outstanding participation", font("CrimsonText-Italic.ttf", 56), (60, 60, 60))
    d.line([(300, 1380), (800, 1380)], fill=(60, 60, 60), width=4)
    d.line([(w - 800, 1380), (w - 300, 1380)], fill=(60, 60, 60), width=4)
    d.text((410, 1400), "Event Head", font=font("Lato-Regular.ttf", 40), fill=(80, 80, 80))
    d.text((w - 690, 1400), "Faculty Advisor", font=font("Lato-Regular.ttf", 40), fill=(80, 80, 80))
    img.save(path, quality=92)


def modern(path):
    w, h = 2339, 1654
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 360, h], fill=(18, 94, 82))
    d.polygon([(360, 0), (560, 0), (360, 360)], fill=(240, 180, 40))
    d.text((520, 220), "CERTIFICATE", font=font("Poppins-Bold.ttf", 140), fill=(18, 94, 82))
    d.text((528, 400), "OF PARTICIPATION", font=font("Poppins-Regular.ttf", 54), fill=(110, 110, 110))
    d.text((528, 600), "Awarded to", font=font("Poppins-Regular.ttf", 56), fill=(70, 70, 70))
    d.text((528, 1050), "For taking part and contributing to the success of the event.",
           font=font("Poppins-Regular.ttf", 48), fill=(70, 70, 70))
    d.line([(528, 1380), (1100, 1380)], fill=(70, 70, 70), width=4)
    d.text((528, 1400), "Organizer", font=font("Poppins-Regular.ttf", 38), fill=(90, 90, 90))
    img.save(path, quality=92)


def dark(path):
    w, h = 2339, 1654
    img = Image.new("RGB", (w, h), (16, 24, 48))
    d = ImageDraw.Draw(img)
    border(d, w, h, (222, 178, 60), 70, 8)
    centered(d, w, 260, "CERTIFICATE OF EXCELLENCE", font("PlayfairDisplaySC-Bold.ttf", 120), (232, 196, 100))
    centered(d, w, 520, "is hereby awarded to", font("CrimsonText-Italic.ttf", 64), (220, 220, 230))
    centered(d, w, 1000, "for exceptional performance and dedication", font("CrimsonText-Italic.ttf", 60), (220, 220, 230))
    img.save(path, quality=92)


if __name__ == "__main__":
    (HERE / "templates").mkdir(exist_ok=True)
    classic(HERE / "templates" / "classic_gold.jpg")
    modern(HERE / "templates" / "modern_green.jpg")
    dark(HERE / "templates" / "midnight_gold.jpg")
    (HERE / "students_sample.csv").write_text(
        "Student Name,Student Email,Personal Email,Roll No,Department\n"
        "avanika kademgari,avanika.k@example.com,,22EC101,ECE\n"
        "ARNAV SHARMA,arnav.sharma@example.com,arnav.personal@example.com,22CS204,CSE\n"
        "Atharva Trivedi,atharva.t@example.com,,22ME310,ME\n"
        "A V Karunya,karunya.av@example.com,,22CS118,CSE\n"
        "M Yash Reddy,yash.reddy@example.com,,22CS150,CSE\n"
        "Venkata Satya Narayana Reddy Kancharla,venkata.k@example.com,,22EE077,EEE\n"
        "Priya Nair,priya.nair@gmial.com,,22IT021,IT\n"
        "Rahul Verma,not-an-email,,22CS099,CSE\n"
        ",missing.name@example.com,,22CS001,CSE\n"
        "Atharva Trivedi,atharva.t@example.com,,22ME310,ME\n"
        "Sneha Rao,,sneha.rao.personal@example.com,22IT044,IT\n",
        encoding="utf-8")
    print("samples created")
