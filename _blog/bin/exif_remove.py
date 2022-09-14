from exif import Image
from exif_delete import exif_delete

fn = "IMG_4106.JPG"

with open("../assets/"+fn,"rb") as src:
    img = Image(src)
    print(img.list_all())

# see https://github.com/john-science/exif_delete/blob/master/exif_delete.py
exif_delete(fn, fn) # overwrite

with open("../assets/"+fn,"rb") as src:
    img = Image(src)
    print(img.list_all())
