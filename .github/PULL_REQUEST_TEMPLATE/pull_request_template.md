### Description
Describe the pull request:
* Why are you opening this pull request?
  * Does the pull reuqest resolve an outstanding bug? If so, mark the pull request with the **bug tag**.
  * Does the pull request introduce new features to CLOVER? If so, mark the pull reuqest with the **feature tag**.
* What version of CLOVER will this be merged into, and what version will it be updated to?

### Linked Issues
This pull request:
* closes issue 1,
* resolves issue 2,

### Unit tests
This pull request:
* modifies the module unit tests for modules X and Y,
* introduces new component unit tests for the Z component.

### Note
Any other information which is useful for the pull request.

## Requirements
### Reviewers
All pull requests must be approved by an administrator of the CLOVER-energy organisation. Make sure to request a review or your pull request will not be approved.
Potential reviewers:
* @BenWinchester
* @philsandwell
* @hamishbeath

### Checks
CLOVER runs a series of automated tests. Run the `./bin/test-clover.sh` helper script to run these prior to opening the pull request. You will not be able to merge your pull request unless all of these automated checks are passing on your code base.
**NOTE:** If you are modifying the automated tests, be sure that you justify this.

**Make sure that you have updated the setup.cfg and** `__version__` **attributes with the new version of CLOVER you are proposing.**
