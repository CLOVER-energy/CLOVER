# CLOVER: Continuous Lifetime Optimisation of Variable Electricity Resources

## Walkthrough
In order to get the best understanding of CLOVER, how it works, and how to use it, it is recommended that you first read this chapter (Overview), and then proceed through the user guide in the order below. You can either read through the user guide in full, start-to-finish, or you can work through your own code in parallel whilst reading through.

* [General Setup](General-Setup.md)
* [Electricity Generation](Electricity-Generation.md)
* [Load Profiles](Load-Profiles.md)
* [Simulation](Simulation.md)

## Overview

### About CLOVER

CLOVER was developed at Imperial College London as a means of investigating how to support rural electrification strategies in developing countries. Under continuous development since 2015, CLOVER has been used for studies of electricity systems in Sub-Saharan Africa, South Asia and South America to explore the potential to provide reliable, affordable and sustainable power to rural and displaced communities.

CLOVER has the capabilities to model electricity systems of any size, from those serving individual households to large communities with diverse uses of energy and beyond, but has most commonly been used for village-scale minigrids serving hundreds of users. Its core functionality is to simulate and optimise systems supplied by any combination of solar, battery storage, diesel generation and a national grid connection to supply energy under specified performance parameters. CLOVER has been used to investigate technical case studies of specific systems, as well as broader analyses of the effects of rural electrification policies, for both academic and practitioner-focused audiences.

### What is CLOVER for?

CLOVER is a software tool for simulating and optimising community-scale electricity systems, typically minigrids to support rural electrification in developing countries. CLOVER allows users to model electricity demand and supply in locations and communities at an hourly resolution, for example allowing them to investigate how a specific electricity system might perform or to find the generation and storage capacity required to meet the needs of the community at the lowest cost. CLOVER can provide an insight into the technical performance, costs, and environmental impact of a system, and allow the user to evaluate many different scenarios to decide on the best way to provide sustainable, affordable and reliable electricity to the community.

### What is CLOVER not for?

Fundamentally, CLOVER is an energy balance model which accounts for the generation and usage of electricity at an hourly resolution. The model is only as good as its data inputs and so the user should be aware of the many caveats that are attached to energy system modelling. CLOVER does not account for technical considerations such as power balancing in real systems, the compatibility of specific electronic components, or the many other practical considerations that would be relevant when designing the exact specifications of a system being deployed in the field. CLOVER can recommend the sizing, design and performance of a potential system, but the user should use this as a guide when using these results to inform real-life systems.

## Learn more

The CLOVER user guide and wiki pages are currently under development. Please refer to the [CLOVER repository](https://github.com/CLOVER-energy/CLOVER) for the latest README and advice on how to set up and use CLOVER.