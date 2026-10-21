"""Immutable prediction bindings; never secret bytes or observed directory edges."""

from dataclasses import dataclass, replace


@dataclass(frozen=True, order=True)
class DelegationBinding:
    controller: str
    principal: str
    impersonated: str
    target: str
    authentication_context: str
    service_context: str
    service: str
    spn: str

    def __post_init__(self):
        if any(not isinstance(v, str) or not v.strip() for v in vars(self).values()):
            raise ValueError("delegation binding requires non-empty strings")
        if self.service != "winrm" or not self.spn.lower().startswith("http/"):
            raise ValueError("supported RBCD scope is WinRM with explicit HTTP SPN")

    def resolve(self, resolver):
        return replace(self, **{k: resolver.resolve(getattr(self, k)) for k in ID_FIELDS})


ID_FIELDS = (
    "controller",
    "principal",
    "impersonated",
    "target",
    "authentication_context",
    "service_context",
)


@dataclass(frozen=True, order=True)
class DelegationArtifact:
    binding: DelegationBinding
    provenance: tuple[str, ...]
    form: str = "password"

    def __post_init__(self):
        if not isinstance(self.binding, DelegationBinding):
            raise ValueError("delegation artifact requires typed binding")
        object.__setattr__(self, "provenance", tuple(self.provenance))
        if not self.provenance or any(
            not isinstance(p, str) or not p.strip() for p in self.provenance
        ):
            raise ValueError("delegation artifact provenance required")
        if self.form != "password":
            raise ValueError("supported RBCD key preparation requires password form")


STATE_FIELDS = frozenset(
    {
        "rbcd_secret",
        "controlled_service",
        "rbcd_descriptor",
        "delegated_context",
    }
)


def decode_artifact(value, resolver):
    if isinstance(value, DelegationArtifact):
        return replace(value, binding=value.binding.resolve(resolver))
    data = dict(value)
    data["binding"] = DelegationBinding(**data["binding"]).resolve(resolver)
    return DelegationArtifact(**data)
