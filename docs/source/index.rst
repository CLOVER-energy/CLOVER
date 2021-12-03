CLOVER documentation and user manual
====================================

Overview
^^^^^^^^^^^^
CLOVER - Continuous Lifetime Optimisation of Variable Electricity Resources - is
a free, open-source tool for modelling, simulating, optimising and analysing the
performance and impacts of electricity systems. Originally designed for off-grid
solar and battery minigrids for rural electrification in developing
countries, CLOVER now includes the functionality to use solar, battery storage,
diesel generation and the national grid to supply power to community-scale
electricity systems.

Its use cases have expanded from simple feasibility studies
to analysis of the long-term impacts and benefits of sustainable rural
electrification, as well as improving the performance and design of real-life
systems currently deployed in the field.

CLOVER is designed to be accessible and work on "ordinary" computers and
laptops and, while the processing speeds will vary, the results will be the
same: it has been run on machines varying in capacities from a Raspberry Pi
to a supercomputer cluster. CLOVER is, and always will be, free to use under an
MIT License.

About this guide
^^^^^^^^^^^^^^^^
This guide aims to provide an introduction to the operation and functionality
of CLOVER, as well as an insight into the kinds of investigations it can be
used for. We have aimed to make it as accessible as possible to new users, who
are assumed to have a basic knowledge of programming (limited experience with
some language, not necessarily Python) and a good knowledge of their chosen
situation (moderate or higher experience with the energy access issues and goals
relevant to their context). More advanced users are, of course, very welcome to
dive deeper into CLOVER's functionality and edit the code to suit their needs.

Each section walks the user through the modules which make up CLOVER, their
core functions, and how they fit together in the entire system. Each module
can be operated independently but we recommend following the order presented in
this guide, as some modules depend on others to function. The sections also
present options for outputs and visualisation of the results.

For coherence with the documentation we recommend that novice users use Spyder
(available by downloading Anaconda) and Python 3.6, which will make this guide
easier to follow and has the requisite packages installed already. This may
also help with the troubleshooting sections throughout this guide.

This guide focuses on the key inputs and outputs of each CLOVER module with the
goal of getting usable, actionable results. For details on the inner workings
of the code, and the exact nature of the functions that it relies on, please
refer to the comments and documentation in the code itself.

For a single PDF document containing all of the information in this guide,
either use the download function (bottom left of the site) or download the user
manual `available here
<https://github.com/phil-sandwell/CLOVER/blob/master/CLOVER%20User%20Manual.pdf>`__.
This site will be continuously updated and should serve as the main reference,
whilst the user manual will be updated after significant updates to CLOVER.

CLOVER is undergoing some big changes to increase its usability. Check back soon
for more updates!

.. toctree::
   :maxdepth: 2

   overview
   general_setup
   electricity_generation
   load
   energy_system_simulation
   optimisation
   get_involved
   license
