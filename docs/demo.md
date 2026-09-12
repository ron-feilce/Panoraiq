# A five-minute walkthrough

1. **Start with the work.** Open the seeded studio. *Observer State* is selected;
   paintings are waiting for their moment. These are explicit fictional demo records.
2. **Show the relationships.** Add a painting and record an open-call submission.
   Change submitted to selected. Filter by painting and selected to find it.
3. **Explain the edition boundary.** Record a manual edition in the work panel. Its
   chain, contract, and token belong to the edition; the work retains its own UUID.
   An owner claim never changes the artist or copyright note. No wallet or minting.
4. **Show the pipeline.** Open a passing PR build. Show the custom images, PostgreSQL
   secondary container, CircleCI test report, and runtime smoke test. Open a failing
   test run to demonstrate release prevention.
5. **Show the release.** Merge through protected `main`, approve the release, and show
   the private S3 archive, manifest, and receipt. The image is promoted from the tested
   workspace, without rebuilding at publication. Explain OIDC and exact-branch trust.
6. **Show restraint.** A documentation-only change skips expensive work. Future wallet
   and IPFS features have a place in the model, but do not complicate the demo.

Before presenting, capture the real CircleCI pipeline URL, Tests tab, successful cloud
receipt, and branch/context restriction settings. The repo code alone does not prove
external account setup or successful deployment. S3 is artifact publication; confirm
the challenge accepts this target if the interviewer expects a running hosted app.
