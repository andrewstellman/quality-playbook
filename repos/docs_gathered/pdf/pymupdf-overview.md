# PyMuPDF Documentation Overview

*Source: https://pymupdf.readthedocs.io/en/latest/*
*Fetched: 2026-04-27*
*Tier: 4 (background context)*

---

> This is a curated overview built from the project's landing page plus several key sub-pages.
> Heading levels and links may have minor formatting artifacts from HTML extraction.

---



## Welcome to PyMuPDF (landing page)

*Sub-page source: https://pymupdf.readthedocs.io/en/latest/*

pymupdf.io
    
      
      
      
    
    
        [English](javaScript:changeLanguage('en'))
        [日本語](javaScript:changeLanguage('ja'))
        [한국어](javaScript:changeLanguage('ko'))
    

    
        [Find **#pymupdf** on **Discord**](https://discord.gg/TSpYGBW4eq)
        [
            
                
                    
                        
                    
                    
                        
                    
                
            
        ](https://discord.gg/TSpYGBW4eq)
    
    
        [Try our forum! ](https://forum.mupdf.com)
    

# Welcome to PyMuPDF[¶](#welcome-to-pymupdf)

PyMuPDF is a high-performance **Python** library for data extraction, analysis, conversion & manipulation of PDF (and other) documents.

PyMuPDF is hosted on [GitHub](https://github.com/pymupdf/PyMuPDF) and registered on [PyPI](https://pypi.org/project/PyMuPDF/).

This documentation covers all versions up to 1.27.2.3.

This software is provided AS-IS with no warranty, either express or implied. This software is distributed under license and may not be copied, modified or distributed except as expressly authorized under the terms of that license. Refer to licensing information at [artifex.com](https://www.artifex.com?utm_source=rtd-pymupdf&utm_medium=rtd&utm_content=footer-link) or contact Artifex Software Inc., 39 Mesa Street, Suite 108A, San Francisco CA 94129, United States for further information.

This documentation covers all versions up to 1.27.2.3.



## About PyMuPDF

*Sub-page source: https://pymupdf.readthedocs.io/en/latest/about.html*

pymupdf.io
    
      
      
      
    
    
        [English](javaScript:changeLanguage('en'))
        [日本語](javaScript:changeLanguage('ja'))
        [한국어](javaScript:changeLanguage('ko'))
    

    
        [Find **#pymupdf** on **Discord**](https://discord.gg/TSpYGBW4eq)
        [
            
                
                    
                        
                    
                    
                        
                    
                
            
        ](https://discord.gg/TSpYGBW4eq)
    
    
        [Try our forum! ](https://forum.mupdf.com)
    

# Features Comparison[¶](#features-comparison)

## Feature Matrix[¶](#feature-matrix)

The following table illustrates how PyMuPDF compares with other typical solutions.
[
](_images/icon-pdf.svg)
[
](_images/icon-svg.svg)
[
](_images/icon-xps.svg)
[
](_images/icon-cbz.svg)
[
](_images/icon-mobi.svg)
[
](_images/icon-epub.svg)
[
](_images/icon-image.svg)
[
](_images/icon-fb2.svg)
[
](_images/icon-txt.svg)
[
](_images/icon-docx.svg)
[
](_images/icon-pptx.svg)
[
](_images/icon-xlsx.svg)
[
](_images/icon-hangul.svg)

    
        Feature
        PyMuPDF
        pikepdf
        PyPDF2
        pdfrw
        pdfplumber / pdfminer
    

    
        Supports Multiple Document Formats

        
            PDF
            XPS
            EPUB
            MOBI
            FB2
            CBZ
            SVG
            TXT
            Image
            
            DOCX
            XLSX
            PPTX
            HWPX
            See [note](#note)
        
        
            PDF
        
        
            PDF
        
        
            PDF
        
        
            PDF
        
    

    
        Implementation
        Python and C
        Python and C++
        Python
        Python
        Python
    

    
        Render Document Pages
        All document types
        No rendering
        No rendering
        No rendering
        No rendering
    

    
        Write Text to PDF Page
        
            

            See:
                [Page.insert_htmlbox](page.html#Page.insert_htmlbox)
                
or:

                [Page.insert_textbox](page.html#Page.insert_textbox )
                
or:

                [TextWriter](textwriter.html)
            
        
        
        
        
        
    

    
        Supports CJK characters
        
        
        
        
        
    

    
        Extract Text
        All document types
        
        PDF only
        
        PDF only
    

    
        Extract Text as Markdown (.md)
        All document types
        
        
        
        
    

    
        Extract Tables
        All document types
        
        
        
        PDF only
    

    
        Extract Vector Graphics
        All document types
        
        
        
        Limited
    

    
        Draw Vector Graphics (PDF)
        
        
        
        
        
    

    
        Based on Existing, Mature Library
        MuPDF
        QPDF
        
        
        
    

    
        Automatic Repair of Damaged PDFs
        
        
        
        
        
    

    
        Encrypted PDFs
        
        
        Limited
        
        Limited
    

    
        Linerarized PDFs
        
        
        
        
        
    

    
        Incremental Updates
        
        
        
        
        
    

    
        Integrates with Jupyter and IPython Notebooks
        
        
        
        
        
    

    
        Joining / Merging PDF with other Document Types
        All document types
        PDF only 
        PDF only 
        PDF only 
        PDF only 
    

    
        OCR API for Seamless Integration with Tesseract
        All document types
        
        
        
        
    

    
        Integrated Checkpoint / Restart Feature (PDF)
        
        
        
        
        
    

    
        PDF Optional Content
        
        
        
        
        
    

    
        PDF Embedded Files
        
        
        Limited
        
        Limited
    

    
        PDF Redactions
        
        
        
        
        
    

    
        PDF Annotations
        Full
        
        Limited
        
        
    

    
        PDF Form Fields
        Create, read, update
        
        Limited, no creation
        
        
    

    
        PDF Page Labels
        
        Read-only
        
        
        
    

    
        Support Font Sub-Setting
        
        
        
        
        
    

Note
[
](_images/icon-docx.svg)
[
](_images/icon-xlsx.svg)
[
](_images/icon-pptx.svg)
[
](_images/icon-hangul.svg)

A note about **Office** document types (DOCX, XLXS, PPTX) and **Hangul** documents (HWPX). These documents can be loaded into PyMuPDF and you will receive a [Document](document.html#document) object.

There are some caveats:

- 

we convert the input to **HTML** to layout the content.

- 

because of this the original page separation has gone.

When saving out the result any faithful representation of the original layout cannot be expected.

Therefore input files are mostly in a form that’s useful for text extraction.

# PyMuPDF Product Suite[¶](#pymupdf-product-suite)

PyMuPDF is the standard version of the library, however there are a family of additional products each with different features and functionality.

**Additional products** in the PyMuPDF product suite are:

- 

PyMuPDF Pro adds support for Office document formats.

- 

PyMuPDF4LLM is optimized for large language model (LLM) applications, providing enhanced text extraction and processing capabilities.

It focuses on layout analysis and semantic understanding, ideal for document conversion and formatting tasks with enhanced results.

Note

All of the products above depend on the same core product - PyMuPDF and therefore have full access to all of its features.
These additional products can be seen as optional extras to the enhance the core PyMuPDF library.

## PyMuPDF Products Comparison[¶](#pymupdf-products-comparison)

The following table illustrates what features the products offer:

PyMuPDF Products Comparison[¶](#id1)

PyMuPDF

PyMuPDF Pro

PyMuPDF4LLM

**Input Documents**

`PDF`, `XPS`, `EPUB`, `CBZ`, `MOBI`, `FB2`, `SVG`, `TXT`, Images (*standard document types*)

*as PyMuPDF* and:
`DOC`/`DOCX`, `XLS`/`XLSX`, `PPT`/`PPTX`, `HWP`/`HWPX`

*as PyMuPDF*

**Output Documents**

Can convert any input document to `PDF`, `SVG` or Image

*as PyMuPDF*

*as PyMuPDF* and:
Markdown (`MD`), `JSON` or `TXT`

**Page Analysis**

Basic page analysis to return document structure

*as PyMuPDF*

Advanced Page Analysis with trained data for enhanced results

**Data extraction**

Basic data extraction with structured layout information and bounding box data

*as PyMuPDF*

Advanced data extraction including layout analysis with semantic understanding and enhanced bounding box data

**Table extraction**

Basic table extraction as part of text extraction

*as PyMuPDF*

Advanced table extraction with cell structure, including support for merged cells and complex layouts

**Image extraction**

Basic image extraction

*as PyMuPDF*

Advanced detection and rendering of image areas on page saving them to disk or embedding in MD output

**Vector extraction**

Vector extraction and clustering

*as PyMuPDF*

Superior detection of “picture” areas

**Popular RAG Integrations**

Langchain, LlamaIndex

*as PyMuPDF*

*as PyMuPDF* and with some additional help methods for RAG workflows

**OCR**

On-demand invocation of built-in Tesseract for text detection on pages or images

*as PyMuPDF*

Automatic OCR based on page content analysis. OCR adapators for popular OCR engines available

# Performance[¶](#performance)

To benchmark PyMuPDF performance against a range of tasks a test suite with a fixed set of [8 PDFs with a total of 7,031 pages](app4.html#appendix4-files-used) containing text & images is used to obtain performance timings.

Here are current results, grouped by task:

**Copying**

This refers to opening a document and then saving it to a new file. This test measures the speed of reading a PDF and re-writing as a new PDF. This process is also at the core of functions like merging / joining multiple documents. The numbers below therefore apply to PDF joining and merging.

The results for all 7,031 pages are:

    

        
            600
            500
            400
            300
            200
            100

⏱seconds
        

        
            
            
            
            
            
            
        

        3.05
        10.54
        33.57
        494.04

    

    
        PyMuPDF
        PDFrw
        PikePDF
        PyPDF2
    

    
        *fastest*
        ←
        ←
        *slowest*
    

**Text Extraction**

This refers to extracting simple, plain text from every page of the document and storing it in a text file.

The results for all 7,031 pages are:

    

        

            400
            300
            200
            100

⏱seconds
        

        

            
            
            
            
        

        8.01
        27.42
        101.64
        227.27

    

    
        PyMuPDF
        XPDF
        PyPDF2
        PDFMiner
    

    
        *fastest*
        ←
        ←
        *slowest*
    

**Rendering**

This refers to making an image (like PNG) from every page of a document at a given DPI resolution. This feature is the basis for displaying a document in a GUI window.

The results for all 7,031 pages are:

    

        
            1000
            800
            600
            400
            200

⏱seconds
        

        
            
            
            
            
            
        

        367.04
        646
        851.52

    

    
        PyMuPDF
        XPDF
        PDF2JPG
    

    
        *fastest*
        ←
        *slowest*
    

Note

For more detail regarding the methodology for these performance timings see: [Performance Comparison Methodology](app4.html#appendix4).



## PyMuPDF Tutorial

*Sub-page source: https://pymupdf.readthedocs.io/en/latest/tutorial.html*

pymupdf.io
    
      
      
      
    
    
        [English](javaScript:changeLanguage('en'))
        [日本語](javaScript:changeLanguage('ja'))
        [한국어](javaScript:changeLanguage('ko'))
    

    
        [Find **#pymupdf** on **Discord**](https://discord.gg/TSpYGBW4eq)
        [
            
                
                    
                        
                    
                    
                        
                    
                
            
        ](https://discord.gg/TSpYGBW4eq)
    
    
        [Try our forum! ](https://forum.mupdf.com)
    

# Tutorial[¶](#tutorial)

This tutorial will show you the use of PyMuPDF, MuPDF in Python, step by step.

Because MuPDF supports not only PDF, but also XPS, OpenXPS, CBZ, CBR, FB2 and EPUB formats, so does PyMuPDF [[1]](#f1). Nevertheless, for the sake of brevity we will only talk about PDF files. At places where indeed only PDF files are supported, this will be mentioned explicitly.

In addition to this introduction, please do visit PyMuPDF’s [YouTube Channel](https://www.youtube.com/@PyMuPDF) which covers most of the following in the form of YouTube “Shorts” and longer videos.

## Importing the Bindings[¶](#importing-the-bindings)

The Python bindings to MuPDF are made available by this import statement. We also show here how your version can be checked:

```
>>> import pymupdf
>>> print(pymupdf.__doc__)
PyMuPDF 1.16.0: Python bindings for the MuPDF 1.16.0 library.
Version date: 2019-07-28 07:30:14.
Built for Python 3.7 on win32 (64-bit).

```

### Note on the Name *fitz*[¶](#note-on-the-name-fitz)

Old versions of PyMuPDF had their **Python** import name as `fitz`. Newer versions use `pymupdf` instead, and offer `fitz` as a fallback so that old code will still work.

The reason for the name `fitz` is a historical curiosity:

The original rendering library for MuPDF was called *Libart*.

*“After Artifex Software acquired the MuPDF project, the development focus shifted on writing a new modern graphics library called “Fitz”. Fitz was originally intended as an R&D project to replace the aging Ghostscript graphics library, but has instead become the rendering engine powering MuPDF.”* (Quoted from [Wikipedia](https://en.wikipedia.org/wiki/MuPDF)).

Note

Use of legacy name `fitz` can fail if defunct pypi.org package `fitz` is installed; see [Problems after installation](installation.html#problems-after-installation).

## Opening a Document[¶](#opening-a-document)

To access a [supported document](how-to-open-a-file.html#supported-file-types), it must be opened with the following statement:

```
doc = pymupdf.open(filename)  # or pymupdf.Document(filename)

```

This creates the [Document](document.html#document) object *doc*. *filename* must be a Python string (or a `pathlib.Path`) specifying the name of an existing file.

It is also possible to open a document from memory data, or to create a new, empty PDF. See [Document](document.html#document) for details. You can also use [Document](document.html#document) as a *context manager*.

A document contains many attributes and functions. Among them are meta information (like “author” or “subject”), number of total pages, outline and encryption information.

## Some [Document](document.html#document) Methods and Attributes[¶](#some-document-methods-and-attributes)

**Method / Attribute**

**Description**

[`Document.page_count`](document.html#Document.page_count)

the number of pages (*int*)

[`Document.metadata`](document.html#Document.metadata)

the metadata (*dict*)

[`Document.get_toc()`](document.html#Document.get_toc)

get the table of contents (*list*)

[`Document.load_page()`](document.html#Document.load_page)

read a [Page](page.html#page)

## Accessing Meta Data[¶](#accessing-meta-data)

PyMuPDF fully supports standard metadata. [`Document.metadata`](document.html#Document.metadata) is a Python dictionary with the following keys. It is available for **all document types**, though not all entries may always contain data. For details of their meanings and formats consult the respective manuals, e.g. [Adobe PDF References](app3.html#adobemanual) for PDF. Further information can also be found in chapter [Document](document.html#document). The meta data fields are strings or `None` if not otherwise indicated. Also be aware that not all of them always contain meaningful data – even if they are not `None`.

Key

Value

producer

producer (producing software)

format

format: ‘PDF-1.4’, ‘EPUB’, etc.

encryption

encryption method used if any

author

author

modDate

date of last modification

keywords

keywords

title

title

creationDate

date of creation

creator

creating application

subject

subject

Note

Apart from these standard metadata, **PDF documents** starting from PDF version 1.4 may also contain so-called *“metadata streams”* (see also [`stream`](glossary.html#stream)). Information in such streams is coded in XML. PyMuPDF deliberately contains no XML components for this purpose (the [PyMuPDF Xml class](xml-class.html#xml) is a helper class intended to access the DOM content of a [Story](story-class.html#story) object), so we do not directly support access to information contained therein. But you can extract the stream as a whole, inspect or modify it using a package like [lxml](https://pypi.org/project/lxml/) and then store the result back into the PDF. If you want, you can also delete this data altogether.

Note

There are two utility scripts in the repository that [metadata import (PDF only)](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/import-metadata/import.py) resp. [metadata export](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/export-metadata/export.py) metadata from resp. to CSV files.

## Working with Outlines[¶](#working-with-outlines)

The easiest way to get all outlines (also called “bookmarks”) of a document, is by loading its *table of contents*:

```
toc = doc.get_toc()

```

This will return a Python list of lists *[[lvl, title, page, …], …]* which looks much like a conventional table of contents found in books.

*lvl* is the hierarchy level of the entry (starting from 1), *title* is the entry’s title, and *page* the page number (1-based!). Other parameters describe details of the bookmark target.

Note

There are two utility scripts in the repository that [toc import (PDF only)](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/import-toc/import.py) resp. [toc export](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/export-toc/export.py) table of contents from resp. to CSV files.

## Working with Pages[¶](#working-with-pages)

[Page](page.html#page) handling is at the core of MuPDF’s functionality.

- 

You can render a page into a raster or vector (SVG) image, optionally zooming, rotating, shifting or shearing it.

- 

You can extract a page’s text and images in many formats and search for text strings.

- 

For PDF documents many more methods are available to add text or images to pages.

First, a [Page](page.html#page) must be created. This is a method of [Document](document.html#document):

```
page = doc.load_page(pno)  # loads page number 'pno' of the document (0-based)
page = doc[pno]  # the short form

```

Any integer `-∞ < pno < page_count` is possible here. Negative numbers count backwards from the end, so *doc[-1]* is the last page, like with Python sequences.

Some more advanced way would be using the document as an **iterator** over its pages:

```
for page in doc:
    # do something with 'page'

# ... or read backwards
for page in reversed(doc):
    # do something with 'page'

# ... or even use 'slicing'
for page in doc.pages(start, stop, step):
    # do something with 'page'

```

Once you have your page, here is what you would typically do with it:

### Inspecting the Links, Annotations or Form Fields of a Page[¶](#inspecting-the-links-annotations-or-form-fields-of-a-page)

Links are shown as “hot areas” when a document is displayed with some viewer software. If you click while your cursor shows a hand symbol, you will usually be taken to the target that is encoded in that hot area. Here is how to get all links:

```
# get all links on a page
links = page.get_links()

```

*links* is a Python list of dictionaries. For details see [`Page.get_links()`](page.html#Page.get_links).

You can also use an iterator which emits one link at a time:

```
for link in page.links():
    # do something with 'link'

```

If dealing with a PDF document page, there may also exist annotations ([Annot](annot.html#annot)) or form fields ([Widget](widget.html#widget)), each of which have their own iterators:

```
for annot in page.annots():
    # do something with 'annot'

for field in page.widgets():
    # do something with 'field'

```

### Rendering a Page[¶](#rendering-a-page)

This example creates a **raster** image of a page’s content:

```
pix = page.get_pixmap()

```

`pix` is a [Pixmap](pixmap.html#pixmap) object which (in this case) contains an **RGB** image of the page, ready to be used for many purposes. Method [`Page.get_pixmap()`](page.html#Page.get_pixmap) offers lots of variations for controlling the image: resolution / DPI, colorspace (e.g. to produce a grayscale image or an image with a subtractive color scheme), transparency, rotation, mirroring, shifting, shearing, etc. For example: to create an **RGBA** image (i.e. containing an alpha channel), specify *pix = page.get_pixmap(alpha=True)*.

A [Pixmap](pixmap.html#pixmap) contains a number of methods and attributes which are referenced below. Among them are the integers `width`, `height` (each in pixels) and `stride` (number of bytes of one horizontal image line). Attribute `samples` represents a rectangular area of bytes representing the image data (a Python `bytes` object).

Note

You can also create a **vector** image of a page by using [`Page.get_svg_image()`](page.html#Page.get_svg_image). Refer to this [Vector Image Support page](https://github.com/pymupdf/PyMuPDF/wiki/Vector-Image-Support) for details.

### Saving the Page Image in a File[¶](#saving-the-page-image-in-a-file)

We can simply store the image in a PNG file:

```
pix.save(f"page-{page.number}.png")

```

### Displaying the Image in GUIs[¶](#displaying-the-image-in-guis)

We can also use it in GUI dialog managers. [`Pixmap.samples`](pixmap.html#Pixmap.samples) represents an area of bytes of all the pixels as a Python bytes object. Here are some examples, find more in the [examples](https://github.com/pymupdf/PyMuPDF-Utilities/tree/master/examples) directory.

#### wxPython[¶](#wxpython)

Consult their documentation for adjustments to RGB(A) pixmaps and, potentially, specifics for your wxPython release:

```
if pix.alpha:
    bitmap = wx.Bitmap.FromBufferRGBA(pix.width, pix.height, pix.samples)
else:
    bitmap = wx.Bitmap.FromBuffer(pix.width, pix.height, pix.samples)

```

#### Tkinter[¶](#tkinter)

Please also see section 3.19 of the [Pillow documentation](https://Pillow.readthedocs.io):

```
from PIL import Image, ImageTk

# set the mode depending on alpha
mode = "RGBA" if pix.alpha else "RGB"
img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
tkimg = ImageTk.PhotoImage(img)

```

The following **avoids using Pillow**:

```
# remove alpha if present
pix1 = pymupdf.Pixmap(pix, 0) if pix.alpha else pix  # PPM does not support transparency
imgdata = pix1.tobytes("ppm")  # extremely fast!
tkimg = tkinter.PhotoImage(data = imgdata)

```

If you are looking for a complete Tkinter script paging through **any supported** document, [here it is!](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/browse-document/browse.py). It can also zoom into pages, and it runs under Python 2 or 3. It requires the extremely handy [PySimpleGUI](https://pypi.org/project/PySimpleGUI/) pure Python package.

#### PyQt4, PyQt5, PySide[¶](#pyqt4-pyqt5-pyside)

Please also see section 3.16 of the [Pillow documentation](https://Pillow.readthedocs.io):

```
from PIL import Image, ImageQt

# set the mode depending on alpha
mode = "RGBA" if pix.alpha else "RGB"
img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
qtimg = ImageQt.ImageQt(img)

```

Again, you also can get along **without using Pillow.** Qt’s `QImage` luckily supports native Python pointers, so the following is the recommended way to create Qt images:

```
from PyQt5.QtGui import QImage

# set the correct QImage format depending on alpha
fmt = QImage.Format_RGBA8888 if pix.alpha else QImage.Format_RGB888
qtimg = QImage(pix.samples_ptr, pix.width, pix.height, fmt)

```

### Extracting Text and Images[¶](#extracting-text-and-images)

We can also extract all text, images and other information of a page in many different forms, and levels of detail:

```
text = page.get_text(opt)

```

Use one of the following strings for *opt* to obtain different formats [[2]](#f2):

- 

**“text”**: (default) plain text with line breaks. No formatting, no text position details, no images.

- 

**“blocks”**: generate a list of text blocks (= paragraphs).

- 

**“words”**: generate a list of words (strings not containing spaces).

- 

**“html”**: creates a full visual version of the page including any images. This can be displayed with your internet browser.

- 

**“dict”** / **“json”**: same information level as HTML, but provided as a Python dictionary or resp. JSON string. See [`TextPage.extractDICT()`](textpage.html#TextPage.extractDICT) for details of its structure.

- 

**“rawdict”** / **“rawjson”**: a super-set of **“dict”** / **“json”**. It additionally provides character detail information like XML. See [`TextPage.extractRAWDICT()`](textpage.html#TextPage.extractRAWDICT) for details of its structure.

- 

**“xhtml”**: text information level as the TEXT version but includes images. Can also be displayed by internet browsers.

- 

**“xml”**: contains no images, but full position and font information down to each single text character. Use an XML module to interpret.

To give you an idea about the output of these alternatives, we did text example extracts. See [Appendix 1: Details on Text Extraction](app1.html#appendix1).

### Searching for Text[¶](#searching-for-text)

You can find out, exactly where on a page a certain text string appears:

```
areas = page.search_for("mupdf")

```

This delivers a list of rectangles (see [Rect](rect.html#rect)), each of which surrounds one occurrence of the string “mupdf” (case insensitive). You could use this information to e.g. highlight those areas (PDF only) or create a cross reference of the document.

Please also do have a look at chapter [Working together: DisplayList and TextPage](coop_low.html#cooperation) and at demo programs [demo.py](https://github.com/pymupdf/PyMuPDF-Utilities/tree/master/demo/demo.py) and [demo-lowlevel.py](https://github.com/pymupdf/PyMuPDF-Utilities/tree/master/demo/demo-lowlevel.py). Among other things they contain details on how the [TextPage](textpage.html#textpage), [Device](device.html#device) and [DisplayList](displaylist.html#displaylist) classes can be used for a more direct control, e.g. when performance considerations suggest it.

## Stories: Generating PDF from HTML Source[¶](#stories-generating-pdf-from-html-source)

The [Story](story-class.html#story) class is a new feature of PyMuPDF version 1.21.0. It represents support for MuPDF’s **“story”** interface.

The following is a quote from the book [“MuPDF Explored”](https://mupdf.com/docs/mupdf_explored.pdf) by Robin Watts from [Artifex](https://www.artifex.com):

*Stories provide a way to easily layout styled content for use with devices, such as those offered by Document Writers (…). The concept of a story comes from desktop publishing, which in turn (…) gets it from newspapers. If you consider a traditional newspaper layout, it will consist of various news articles (stories) that are laid out into multiple columns, possibly across multiple pages.*

*Accordingly, MuPDF uses a story to represent a flow of text with styling information. The user of the story can then supply a sequence of rectangles into which the story will be laid out, and the positioned text can then be drawn to an output device. This keeps the concept of the text itself (the story) to be separated from the areas into which the text should be flowed (the layout).*

Note

A Story works somewhat similar to an internet browser: It faithfully parses and renders HTML hypertext and also optional stylesheets (CSS). But its **output is a PDF** – not web pages.

When creating a [Story](story-class.html#story), the input from up to three different information sources is taken into account. All these items are optional.

1. 

HTML source code, either a Python string or **created by the script** using methods of [Xml](xml-class.html#xml).

2. 

CSS (Cascaded Style Sheet) source code, provided as a Python string. CSS can be used to provide styling information (text font size, color, etc.) like it would happen for web pages. Obviously, this string may also be read from a file.

3. 

An [Archive](archive-class.html#archive) **must be used** whenever the DOM references images, or uses text fonts except the standard [PDF Base 14 Fonts](app3.html#base-14-fonts), CJK fonts and the NOTO fonts generated into the PyMuPDF binary.

The [API](xml-class.html#xml) allows creating DOMs completely from scratch, including desired styling information. It can also be used to modify or extend **provided** HTML: text can be deleted or replaced, or its styling can be changed. Text – for example extracted from databases – can also be added and fill template-like HTML documents.

It is **not required** to provide syntactically complete HTML documents: snippets like `<b>Hello` are fully accepted, and many / most syntax errors are automatically corrected.

After the HTML is considered complete, it can be used to create a PDF document. This happens via the new [DocumentWriter](document-writer-class.html#documentwriter) class. The programmer calls its methods to create a new empty page, and passes rectangles to the Story to fill them.

The story in turn will return completion codes indicating whether or not more content is waiting to be written. Which part of the content will land in which rectangle or on which page is automatically determined by the story itself – it cannot be influenced other than by providing the rectangles.

Please see the [Stories recipes](recipes-stories.html#recipesstories) for a number of typical use cases.

## PDF Maintenance[¶](#pdf-maintenance)

PDFs are the only document type that can be **modified** using PyMuPDF. Other file types are read-only.

However, you can convert **any document** (including images) to a PDF and then apply all PyMuPDF features to the conversion result. Find out more here [`Document.convert_to_pdf()`](document.html#Document.convert_to_pdf), and also look at the demo script [pdf-converter.py](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/convert-document/convert.py) which can convert any [supported document](how-to-open-a-file.html#supported-file-types) to PDF.

[`Document.save()`](document.html#Document.save) always stores a PDF in its current (potentially modified) state on disk.

You normally can choose whether to save to a new file, or just append your modifications to the existing one (“incremental save”), which often is very much faster.

The following describes ways how you can manipulate PDF documents. This description is by no means complete: much more can be found in the following chapters.

### Modifying, Creating, Re-arranging and Deleting Pages[¶](#modifying-creating-re-arranging-and-deleting-pages)

There are several ways to manipulate the so-called **page tree** (a structure describing all the pages) of a PDF:

[`Document.delete_page()`](document.html#Document.delete_page) and [`Document.delete_pages()`](document.html#Document.delete_pages) delete pages.

[`Document.copy_page()`](document.html#Document.copy_page), [`Document.fullcopy_page()`](document.html#Document.fullcopy_page) and [`Document.move_page()`](document.html#Document.move_page) copy or move a page to other locations within the same document.

[`Document.select()`](document.html#Document.select) shrinks a PDF down to selected pages. Parameter is a sequence [[3]](#f3) of the page numbers that you want to keep. These integers must all be in range *0 <= i < page_count*. When executed, all pages **missing** in this list will be deleted. Remaining pages will occur **in the sequence and as many times (!) as you specify them**.

So you can easily create new PDFs with

- 

the first or last 10 pages,

- 

only the odd or only the even pages (for doing double-sided printing),

- 

pages that **do** or **don’t** contain a given text,

- 

reverse the page sequence, …

… whatever you can think of.

The saved new document will contain links, annotations and bookmarks that are still valid (i.a.w. either pointing to a selected page or to some external resource).

[`Document.insert_page()`](document.html#Document.insert_page) and [`Document.new_page()`](document.html#Document.new_page) insert new pages.

Pages themselves can moreover be modified by a range of methods (e.g. page rotation, annotation and link maintenance, text and image insertion).

### Joining and Splitting PDF Documents[¶](#joining-and-splitting-pdf-documents)

Method [`Document.insert_pdf()`](document.html#Document.insert_pdf) copies pages **between different** PDF documents. Here is a simple **joiner** example (*doc1* and *doc2* being opened PDFs):

```
# append complete doc2 to the end of doc1
doc1.insert_pdf(doc2)

```

Here is a snippet that **splits** *doc1*. It creates a new document of its first and its last 10 pages:

```
doc2 = pymupdf.open()                 # new empty PDF
doc2.insert_pdf(doc1, to_page = 9)  # first 10 pages
doc2.insert_pdf(doc1, from_page = len(doc1) - 10) # last 10 pages
doc2.save("first-and-last-10.pdf")

```

More can be found in the [Document](document.html#document) chapter. Also have a look at [PDFjoiner.py](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/join-documents/join.py).

### Embedding Data[¶](#embedding-data)

PDFs can be used as containers for arbitrary data (executables, other PDFs, text or binary files, etc.) much like ZIP archives.

PyMuPDF fully supports this feature via [Document](document.html#document) `embfile_*` methods and attributes. For some detail read [Appendix 2: Considerations on Embedded Files](app2.html#appendix2), consult the Wiki on [dealing with embedding files](https://github.com/pymupdf/PyMuPDF/wiki/Dealing-with-Embedded-Files), or the example scripts [embedded-copy.py](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/copy-embedded/copy.py), [embedded-export.py](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/export-embedded/export.py), [embedded-import.py](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/import-embedded/import.py), and [embedded-list.py](https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/list-embedded/list.py).

### Saving[¶](#saving)

As mentioned above, [`Document.save()`](document.html#Document.save) will **always** save the document in its current state.

You can write changes back to the **original PDF** by specifying option `incremental=True`. This process is (usually) **extremely fast**, since changes are **appended to the original file** without completely rewriting it.

[`Document.save()`](document.html#Document.save) options correspond to options of MuPDF’s command line utility *mutool clean*, see the following table.

**Save Option**

**mutool**

**Effect**

garbage=1

g

garbage collect unused objects

garbage=2

gg

in addition to 1, compact [`xref`](glossary.html#xref) tables

garbage=3

ggg

in addition to 2, merge duplicate objects

garbage=4

gggg

in addition to 3, merge duplicate stream content

clean=True

cs

clean and sanitize content streams

deflate=True

z

deflate uncompressed streams

deflate_images=True

i

deflate image streams

deflate_fonts=True

f

deflate fontfile streams

ascii=True

a

convert binary data to ASCII format

linear=True

l

create a linearized version

expand=True

d

decompress all streams

Note

For an explanation of terms like `object`, `stream`, `xref` consult the [Glossary](glossary.html#glossary) chapter.

For example, `mutool clean -ggggz file.pdf` yields excellent compression results. It corresponds to `doc.save(filename, garbage=4, deflate=True)`.

## Closing[¶](#closing)

It is often desirable to “close” a document to relinquish control of the underlying file to the OS, while your program continues.

This can be achieved by the [`Document.close()`](document.html#Document.close) method. Apart from closing the underlying file, buffer areas associated with the document will be freed.

## Further Reading[¶](#further-reading)

Also have a look at PyMuPDF’s [Wiki](https://github.com/pymupdf/PyMuPDF/wiki) pages. Especially those named in the sidebar under title **“Recipes”** cover over 15 topics written in “How-To” style.

This document also contains a [FAQ](faq.html#faq). This chapter has close connection to the aforementioned recipes, and it will be extended with more content over time.

Footnotes

[[1](#id2)]

PyMuPDF lets you also open several image file types just like normal documents. See section [Supported Input Image Formats](pixmap.html#imagefiles) in chapter [Pixmap](pixmap.html#pixmap) for more comments.

[[2](#id3)]

[`Page.get_text()`](page.html#Page.get_text) is a convenience wrapper for several methods of another PyMuPDF class, [TextPage](textpage.html#textpage). The names of these methods correspond to the argument string passed to [`Page.get_text()`](page.html#Page.get_text) :  *Page.get_text(“dict”)* is equivalent to *TextPage.extractDICT()* .

[[3](#id4)]

“Sequences” are Python objects conforming to the sequence protocol. These objects implement a method named *__getitem__()*. Best known examples are Python tuples and lists. But *array.array*, *numpy.array* and PyMuPDF’s “geometry” objects ([Operator Algebra for Geometry Objects](algebra.html#algebra)) are sequences, too. Refer to [Using Python Sequences as Arguments in PyMuPDF](app3.html#sequencetypes) for details.

This software is provided AS-IS with no warranty, either express or implied. This software is distributed under license and may not be copied, modified or distributed except as expressly authorized under the terms of that license. Refer to licensing information at [artifex.com](https://www.artifex.com?utm_source=rtd-pymupdf&utm_medium=rtd&utm_content=footer-link) or contact Artifex Software Inc., 39 Mesa Street, Suite 108A, San Francisco CA 94129, United States for further information.

This documentation covers all versions up to 1.27.2.3.

