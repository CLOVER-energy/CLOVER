Introduction
============

This guide provides a guide to using CLOVER following the initial
download. CLOVER is free and open-source for all to use, and the latest
version of CLOVER is available on
`GitHub <https://github.com/phil-sandwell/CLOVER>`__. Periodic updates
to the code are also posted on Github to increase its functionality and
fix bugs. This document provides examples of how to run the code, how
the different modules and functions operate, and the kinds of outputs
that can be obtained.

About CLOVER
------------

CLOVER was developed at Imperial College London as a means of
investigating how to support rural electrification strategies in
developing countries. Under continuous development since 2015, CLOVER
has been used for studies of electricity systems in Sub-Saharan Africa,
South Asia and South America to explore the potential to provide
reliable, affordable and sustainable power to rural and displaced
communities.

CLOVER has the capabilities to model electricity systems of any size,
from those serving individual households to large communities with
diverse uses of energy and beyond, but has most commonly been used for
village-scale minigrids serving hundreds of users. Its core
functionality is to simulate and optimise systems supplied by any
combination of solar, battery storage, diesel generation and a national
grid connection to supply energy under specified performance parameters.
CLOVER has been used to investigate technical case studies of specific
systems, as well as broader analyses of the effects of rural
electrification policies, for both academic and practitioner-focused
audiences.

Some open-source examples of how CLOVER has been used include:

* Using solar and battery storage minigrids to support an unreliable grid network in rural India (`available here <https://www.sciencedirect.com/science/article/pii/S1876610217345101>`__)
* Investigating how to support rural electrification policies in Rwanda and Nepal (`available here <http://www.imperial.ac.uk/grantham/publications/energy-and-low-carbon-futures/supporting-rural-electrification-in-developing-countries.php>`__)
* Exploring the opportunities for solar energy to offset diesel generation in refugee camps (`available here <https://spiral.imperial.ac.uk:8443/bitstream/10044/1/77296/6/Sustainable%20mini-grid%20systems%20in%20refugee%20gamps%20-%20Rwanda%20-%20web.pdf>`__)

CLOVER has also been used for investigations in several PhD theses (`one
example here <https://doi.org/10.25560/58881>`__) and Master’s theses.
The latter has included investigations into:

* Using minigrids to provide power to rural entrepreneurs in Rwanda
* Using solar power to provide electricity to health centres in remote areas of Kenya
* The opportunities for using health centres as anchor load clients in rural India
* Options for supporting electricity for educational purposes at a women’s education centre in Senegal
* The benefits of providing electricity for açaí processing in rural Brazil
* System design options for minigrids in refugee camps in Djibouti

More recently, CLOVER has been expanded to include clean- and hot-water system
modelling, with ongoing MSc theses investigating the inclusion of heating and
cooling loads in CLOVER.

What is CLOVER for?
~~~~~~~~~~~~~~~~~~~

CLOVER is a software tool for simulating and optimising community-scale
electricity, clean- and hot-water systems, typically minigrids to support rural
electrification in developing countries. CLOVER allows users to model
electricity, clean- and hot-water demand and supply in locations and communities
at an hourly resolution, for example allowing them to investigate how a specific
electricity system might perform or to find the generation and storage
capacity required to meet the needs of the community at the lowest cost.
CLOVER can provide an insight into the technical performance, costs, and
environmental impact of a system, and allow the user to evaluate many
different scenarios to decide on the best way to provide sustainable,
affordable and reliable electricity to the community.

What is CLOVER not for?
~~~~~~~~~~~~~~~~~~~~~~~

Fundamentally, CLOVER is an energy balance model which accounts for the
generation and usage of electricity at an hourly resolution. The model
is only as good as its data inputs and so the user should be aware of
the many caveats that are attached to energy system modelling. CLOVER
does not account for technical considerations such as power balancing in
real systems, the compatibility of specific electronic components, or
the many other practical considerations that would be relevant when
designing the exact specifications of a system being deployed in the
field. CLOVER can recommend the sizing, design and performance of a
potential system, but the user should use this as a guide when using
these results to inform real-life systems.

Getting CLOVER on your computer
-------------------------------

Downloading CLOVER
~~~~~~~~~~~~~~~~~~

Go to https://github.com/phil-sandwell/CLOVER to download the latest stable
version of CLOVER by clicking the “Clone or download” button and
selecting “Download ZIP”. This will download a zipped folder containing
all of the files you need to get started.

CLOVER file structure
~~~~~~~~~~~~~~~~~~~~~

The file structure from the download has two branches:

* a *src* branch which contains Python files that constitute the source code behind CLOVER which are used to generate outputs and perform simulations and optimisations,
* a *locations* branch that describes individual locations and the specifics of a given scenario being investigated.

An example location, *Bahraich* in India, is included in the initial
download for reference. New locations can be set up using the helper script
provided. It is recommended that the user makes their first new location
utilising the helper script provided and its default values which can then be
adjusted as needed.

CLOVER modules
~~~~~~~~~~~~~~

CLOVER is designed to be modular, with each module or script performing
a specific function (e.g. calculating the load of a community, getting
the solar generation, or simulating the performance of a system). CLOVER should
be run as a single compomnent or as an installed package.

Running CLOVER
~~~~~~~~~~~~~~

The recommended integrated development environment (IDE) for running
CLOVER is `Spyder <https://www.spyder-ide.org>`__ although many others
are available. This IDE is software which allows the user to view and
edit scripts, run the code, run individual functions, and view the
outputs easily. The easiest way to get Spyder is to download
`Anaconda <https://www.anaconda.com/distribution>`__ which includes
Spyder as a default package. CLOVER is written using Python 3.7 so the
user should make sure that their Python environment uses this version;
the packages that CLOVER uses are all included in the Anaconda
distribution.

About this guide
----------------

This document is designed to guide a new user from the point of
downloading CLOVER to being able to run their own simulations and
optimisations. It contains worked examples of using the code and, owing
to the format of the document, several pieces of code are included in
this document which will not be necessary when running CLOVER using
Spyder. These include viewing the input CSV and YAML files (which can be done in
your file browser) and executing the code (which can be done by clicking
the green arrow in Spyder) but are necessary to compile the code here.
These will be highlighted as they come up.

Throughout this guide the **text in bold** highlights the steps you need
to take to set up CLOVER, *text in italics* refers to the names of
modules or other parts of the model structure, and ``text in code``
refers to variables or functions.
