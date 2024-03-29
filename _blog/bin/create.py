# read through markdown posts
# generate index.html for each post
#   title from inside markdown
#   expect markdown to follow a template
# place file into folder with corresponding slug title
#   markdown posts should be of format `000-slug-title.md`
# create symbolic link(s) for image(s)
# update search index
# update home index page

import time
start = time.time()

# imports
import os, re, shutil, markdown
from exif_delete import exif_delete
from argparse import ArgumentParser

# https://stackoverflow.com/a/1009864
parser = ArgumentParser()
parser.add_argument(
    "-v", "--verbose",
    action="store_true", dest="verbose", default=False,
    help="print status messages to stdout"
)
args = parser.parse_args()
if args.verbose:
    print("Running verbosely")

# markdown image extension
class ImageTreeprocessor(markdown.treeprocessors.Treeprocessor):
    # def __init__(self, md, config):
    #     self.md = md
    #     super().__init__(md)
    #     # other config options?
    def run(self, root):
        for x in root.iter():
            if x.tag == "img":
                self.md.Img.append(x.attrib['src'])
            # else:
            #     for child in x:
            #         print(child.tag, child.text)
            #         self.run(child)
class ImageScraper(markdown.extensions.Extension):
    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        self.md = md
        #self.reset()
        # default priorities
        # >>> md.treeprocessors._priority
        # [PriorityItem(name='inline', priority=20), PriorityItem(name='prettify', priority=10)]
        # smaller priority equates to getting ran last
        md.treeprocessors.register(ImageTreeprocessor(md),'ImageTreeprocessor',1)
    def reset(self):
        #print('---called reset')
        self.md.Img = []
    #
#
md = markdown.Markdown(extensions=['tables','fenced_code','meta',ImageScraper()])

# variables
POSTS = "posts"
SITE = "templates"
IMAGES = "assets"
OUTPUT = "../blog"
TEMPLATE_PAGE = os.path.join(SITE,"post.html")
TEMPLATE_HOME = os.path.join(SITE,"home.html")
TITLE = "{% TITLE %}"
P_BODY = "{% BODY %}" # make regex?
M_LIST = "{% LIST %}"
M_TAG_LIST = "{% TAG_LIST %}"

# git-style last-updated (TODO)

# command-line flags (TODO)
# - remake everything
# - auto-allow-delete
# - create only one (input the post you wanna create)
# - clean (remove) non-existant posts (maybe?)

# assume this file is executed in the parent directory `/blog`
assert os.path.basename(os.getcwd()) == "_blog", "you're in the wrong directory!"

# assume everything in POSTS is a post to be created
if args.verbose:
    print("Generating posts")
prog = re.compile("\d*-(.+)\.md") # error on invalid format?
with open(TEMPLATE_PAGE,"r") as f:
    template = f.read() # could move to top?
m = [] # for later
tags = {}
for post in os.listdir(POSTS): # no guaranteed order
    if args.verbose:
        print(post)
    # cmd flags, test for directory, del if need be, etc...
    #
    slug = prog.match(post).group(1) # make safer?
    slug_dir = os.path.join(OUTPUT,slug)
    if os.path.exists(slug_dir):
        shutil.rmtree(slug_dir)
    os.makedirs(slug_dir)
    #
    with open(os.path.join(POSTS,post),"r") as f:
        # i hate python variables (the whole global scope thing)
        p = md.convert(f.read())
    #
    if 'no' in md.Meta.get("publish"): # skip unpublished posts
        continue
    # show metadata (TODO, maybe make this collapsable?)
    if args.verbose:
        print(md.Meta)
    p += "<hr>\n<pre><code class='txt'>METADATA\n--------\n"+"\n".join([x+": "+"|".join(md.Meta[x]) for x in md.Meta])+"\n</code></pre>"
    #
    output = template.replace(TITLE, md.Meta.get("title")[0])
    output = output.replace(P_BODY, p)
    with open(os.path.join(slug_dir,"index.html"),"w") as f:
        f.write(output)
    #
    # symlink image(s)
    if args.verbose:
        print(md.Img)
    for image in md.Img:
        # remote metadata from image
        fn = os.path.join(IMAGES,image)
        exif_delete(fn, fn) # overwrite
        #print(os.path.join(slug_dir,image))
        # link is with respect to destination
        # print(os.getcwd())
        #os.symlink(os.path.join("..",fn), os.path.join(slug_dir,image))
        # we'll see if this works
        #
        # gotta figure out how to follow symlinks for html
        # for now, just copy the image?
        shutil.copy(fn, os.path.join(slug_dir,image))
        #
        # yeah, TODO make nginx follow symlinks
        # this is good?
    #
    # save data
    m.append([post,slug,md.Meta]) # list so we can sort later (post == key)
    for tag in md.Meta['tags']:
        tags[tag] = tags.get(tag,0) + 1
    # done
    md.reset()
#

# TODO -- fix the YAML parser in markdown package
# it returns all values inside a list, which is stupid
# -- i read the docs, and they did it to "preserve newlines"
# -- still kinda dumb, but whatever it works

# indexing
# (update home for now)
if args.verbose:
    print("Writing home index.html")
with open(TEMPLATE_HOME,"r") as f:
    template = f.read()
with open(os.path.join(OUTPUT,"index.html"),"w") as f:
    m.sort(reverse=True)
    # tag delimiter == |
    m = ["<li data-tags='"+"|".join(x[2]['tags'])+"'><a href='"+x[1]+"/'>("+x[2]['date'][0]+") "+x[2]['title'][0]+"</a></li>" for x in m]
    output = template.replace(M_LIST, "<ol id='posts' start='"+str(len(m)-1)+"' reversed>" + "\n".join(m) + "</ol>")
    tags = ["<li data-count='"+str(tags[x])+"' data-tag='"+x+"' class='active'>"+x+" ("+str(tags[x])+")"+"</li>" for x in tags]
    output = output.replace(M_TAG_LIST, "<ul class='list-inline' id='tag-list'>"+ "\n".join(tags) +"</ul>")
    f.write(output)
#

# copy over css/js
if args.verbose:
    print("Copying over css/js")
for t in ["css", "js"]:
    p = os.path.join(OUTPUT,f"_{t}")
    if os.path.exists(p):
        shutil.rmtree(p)
    shutil.copytree(os.path.join(".",t), p)

print("{:.3f} sec, {} posts".format(time.time() - start, len(m)))
