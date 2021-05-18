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

EXCLUDED = ['.htaccess','index.html','gen.py']

import os
from mako.template import Template

files = [(fname,sizeof_fmt(os.path.getsize(fname))) for fname in sorted(os.listdir(".")) if fname not in EXCLUDED]
header = os.path.basename(os.path.abspath(".")) # might need to change if we move /docs

with open("index.html","w") as f:
    f.write(Template(INDEX_TEMPLATE).render(files=files, header=header))
