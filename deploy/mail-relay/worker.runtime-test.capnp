using Workerd = import "/workerd/workerd.capnp";

# Offline integration test: all outbound requests go to the mock service.
# Run: workerd test deploy/mail-relay/worker.runtime-test.capnp relay-test
const config :Workerd.Config = (
  services = [
    (name = "relay-test", worker = (
      modules = [
        (name = "test.mjs", esModule = embed "worker.runtime-test.mjs"),
        (name = "worker.mjs", esModule = embed "worker.mjs")
      ],
      compatibilityDate = "2026-09-13",
      globalOutbound = "mock-server"
    )),
    (name = "mock-server", worker = (
      modules = [
        (name = "test.mjs", esModule = embed "worker.runtime-test.mjs"),
        (name = "worker.mjs", esModule = embed "worker.mjs")
      ],
      compatibilityDate = "2026-09-13"
    ))
  ]
);
