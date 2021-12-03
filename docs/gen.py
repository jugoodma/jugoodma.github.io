import os, fnmatch
from mako.template import Template

# https://stackoverflow.com/a/1094933
def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

# https://stackoverflow.com/a/39402604
INDEX_TEMPLATE = r"""
<html>
    <head>
        <title>Index of /${header}</title>
    </head>
    <body>
        <h1>Index of /${header}</h1>
        <table>
            <tbody>
                <tr>
                    <th>Name</th>
                    <th>Size</th>
                </tr>
                <tr>
                    <td><a href="../">../</a></td>
                    <td></td>
                </tr>
                % for name,size in files:
                <tr>
                    <td><a href="${name}">${name}</a></td>
                    <td style="text-align:right">${size}</td>
                </tr>
                % endfor
            </tbody>
        </table>
        <p><em>This is a statically-generated index file, and may not be up-to-date.</em></p>
    </body>
</html>
"""

# generate list of EXCLUDED files using gitignore
EXCLUDED = {'.htaccess':True,'index.html':True,'gen.py':True}
curr_dir = os.listdir(".")
with open(".gitignore","r") as f:
    for line in f:
        line = line.strip()
        if line[0] == "!":
            # include
            line = line[1:]
            for fn in curr_dir:
                if fnmatch.fnmatch(fn, line):
                    EXCLUDED[fn] = False
        else:
            # exclude
            for fn in curr_dir:
                if fnmatch.fnmatch(fn, line):
                    EXCLUDED[fn] = True
EXCLUDED = [k for k in EXCLUDED if EXCLUDED[k]]
print("ignoring files: "+str(EXCLUDED))

files = [(fname,sizeof_fmt(os.path.getsize(fname))) for fname in sorted(os.listdir(".")) if fname not in EXCLUDED]
header = os.path.basename(os.path.abspath(".")) # might need to change if we move /docs

with open("index.html","w") as f:
    f.write(Template(INDEX_TEMPLATE).render(files=files, header=header))
