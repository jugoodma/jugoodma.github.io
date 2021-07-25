# read through markdown posts
# generate index.html for each post
#   title from inside markdown
#   expect markdown to follow a template
# place file into folder with corresponding slug title
#   markdown posts should be of format `000-slug-title.md`
# create symbolic link(s) for image(s)
# update search index
# update home index page

# imports
import os
import re
import shutil
import markdown

# markdown image extension
class ImageTreeprocessor(markdown.treeprocessors.Treeprocessor):
    def __init__(self, md, config):
        self.md = md
        super().__init__(md)
        # other config options?
    def run(self, root):
        for image in root.findall('.//img'):
            self.md.Img.append(image.attrib['src'])
class ImageScraper(markdown.extensions.Extension):
    def extendMarkdown(self, md, md_globals):
        md.registerExtension(self)
        self.md = md
        #self.reset()
        md.treeprocessors.add('img',ImageTreeprocessor(md,None),'_end')
    def reset(self):
        #print('---called reset')
        self.md.Img = []
    #
#
md = markdown.Markdown(extensions=['tables','fenced_code','meta',ImageScraper()])

# variables
POSTS = "_posts"
SITE = "_site"
IMAGES = "_img"
TEMPLATE_PAGE = os.path.join(SITE,"template-post.html")
TEMPLATE_HOME = os.path.join(SITE,"template-home.html")
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
assert os.path.basename(os.getcwd()) == "blog", "you're in the wrong directory!"

# assume any folder in `/blog`
#   except ones that start with an underscore
# is a post
#
# assume everything in POSTS is a post to be created
prog = re.compile("\d*-(.+)\.md") # error on invalid format?
with open(TEMPLATE_PAGE,"r") as f:
    template = f.read() # could move to top?
m = [] # for later
tags = {}
for post in os.listdir(POSTS): # no guaranteed order
    print(post)
    # cmd flags, test for directory, del if need be, etc...
    #
    slug = prog.match(post).group(1) # make safer?
    slug_dir = os.path.join(".",slug)
    if os.path.exists(slug_dir):
        shutil.rmtree(slug_dir)
    os.makedirs(slug_dir)
    #
    with open(os.path.join(POSTS,post),"r") as f:
        # i hate python variables (the whole global scope thing)
        p = md.convert(f.read())
    #
    # show metadata (todo, maybe make this collapsable?)
    p += "<hr>\n<pre><code class='txt'>METADATA\n--------\n"+"\n".join([x+": "+"|".join(md.Meta[x]) for x in md.Meta])+"\n</code></pre>"
    #
    output = template.replace(P_BODY, p)
    with open(os.path.join(slug_dir,"index.html"),"w") as f:
        f.write(output)
    #
    # symlink image(s)
    for image in md.Img:
        #print(os.path.join(slug_dir,image))
        # link is with respect to destination
        os.symlink(os.path.join("..",IMAGES,image), os.path.join(slug_dir,image))
        # we'll see if this works
        #
        # gotta figure out how to follow symlinks for html
        # for now, just copy the image
        #shutil.copy(os.path.join(IMAGES,image), os.path.join(slug_dir,image))
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
with open(TEMPLATE_HOME,"r") as f:
    template = f.read()
with open("index.html","w") as f:
    m.sort(reverse=True)
    # tag delimiter == |
    m = ["<li data-tags='"+"|".join(x[2]['tags'])+"'><a href='"+x[1]+"/'>("+x[2]['date'][0]+") "+x[2]['title'][0]+"</a></li>" for x in m]
    output = template.replace(M_LIST, "<ol id='posts' start='"+str(len(m)-1)+"' reversed>" + "\n".join(m) + "</ol>")
    tags = ["<li data-count='"+str(tags[x])+"' data-tag='"+x+"' class='active'>"+x+" ("+str(tags[x])+")"+"</li>" for x in tags]
    output = output.replace(M_TAG_LIST, "<ul class='list-inline' id='tag-list'>"+ "\n".join(tags) +"</ul>")
    f.write(output)
#
