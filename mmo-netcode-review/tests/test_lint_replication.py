"""lint_replication.py 단위 테스트: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import lint_replication as lr  # noqa: E402

GOOD_H = """
#pragma once
enum class EState : uint8 { Idle, Dead };

UCLASS()
class MYGAME_API AHero : public ACharacter
{
    GENERATED_BODY()
public:
    UPROPERTY(ReplicatedUsing = OnRep_Health, BlueprintReadOnly, meta = (ClampMin = "0"))
    float Health = 100.f;

    UPROPERTY(Replicated)
    TObjectPtr<AActor> Target;

    UPROPERTY(EditAnywhere)
    int32 NotReplicated;

    UFUNCTION()
    void OnRep_Health();

    UFUNCTION(Server, Reliable, WithValidation)
    void ServerUseSkill(int32 SkillId, AActor* InTarget);

    UFUNCTION(NetMulticast, Unreliable)
    void MulticastPlayHitFx(FVector Location);
};
"""
GOOD_CPP = """
void AHero::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const
{
    Super::GetLifetimeReplicatedProps(Out);
    DOREPLIFETIME_CONDITION(AHero, Health, COND_None);
    DOREPLIFETIME(AHero, Target);
}
"""


def rules(headers, cpps=None):
    return sorted(f["rule"] for f in lr.lint(headers, cpps or {}))


class Lint(unittest.TestCase):
    def test_clean_code_has_no_findings(self):
        self.assertEqual(rules({"Hero.h": GOOD_H}, {"Hero.cpp": GOOD_CPP}), [])

    def test_missing_registration(self):
        cpp = GOOD_CPP.replace("DOREPLIFETIME(AHero, Target);", "")
        f = lr.lint({"Hero.h": GOOD_H}, {"Hero.cpp": cpp})
        self.assertEqual([x["rule"] for x in f], ["NET001"])
        self.assertIn("AHero::Target", f[0]["message"])
        self.assertEqual(f[0]["line"], 13)

    def test_commented_out_registration_does_not_count(self):
        cpp = GOOD_CPP.replace("DOREPLIFETIME(AHero, Target);", "// DOREPLIFETIME(AHero, Target);")
        self.assertEqual(rules({"Hero.h": GOOD_H}, {"Hero.cpp": cpp}), ["NET001"])

    def test_active_override_is_not_registration(self):
        cpp = GOOD_CPP.replace("DOREPLIFETIME(AHero, Target);", "DOREPLIFETIME_ACTIVE_OVERRIDE(AHero, Target, true);")
        self.assertEqual(rules({"Hero.h": GOOD_H}, {"Hero.cpp": cpp}), ["NET001"])

    def test_missing_onrep_declaration(self):
        h = GOOD_H.replace("void OnRep_Health();", "")
        self.assertEqual(rules({"Hero.h": h}, {"Hero.cpp": GOOD_CPP}), ["NET002"])

    def test_reliable_multicast(self):
        h = GOOD_H.replace("NetMulticast, Unreliable", "NetMulticast, Reliable")
        self.assertEqual(rules({"Hero.h": h}, {"Hero.cpp": GOOD_CPP}), ["NET003"])

    def test_server_rpc_without_validation_is_info(self):
        h = GOOD_H.replace(", WithValidation", "")
        f = lr.lint({"Hero.h": h}, {"Hero.cpp": GOOD_CPP})
        self.assertEqual([(x["rule"], x["severity"]) for x in f], [("NET004", "info")])

    def test_client_sends_authoritative_value(self):
        h = GOOD_H.replace("int32 SkillId, AActor* InTarget", "AActor* InTarget, float DamageAmount, int32 NewHP = 0")
        f = lr.lint({"Hero.h": h}, {"Hero.cpp": GOOD_CPP})
        self.assertEqual([x["rule"] for x in f], ["NET005"])
        self.assertIn("DamageAmount", f[0]["message"])
        self.assertIn("NewHP", f[0]["message"])

    def test_token_match_is_word_based(self):
        # 'Expected', 'Explosion'은 'exp'로 걸리면 안 된다
        h = GOOD_H.replace("int32 SkillId, AActor* InTarget", "int32 ExpectedIndex, FVector ExplosionLocation")
        self.assertEqual(rules({"Hero.h": h}, {"Hero.cpp": GOOD_CPP}), [])

    def test_replicated_array_is_info(self):
        h = GOOD_H.replace("TObjectPtr<AActor> Target;", "TArray<FItemSlot> Target;")
        self.assertEqual(rules({"Hero.h": h}, {"Hero.cpp": GOOD_CPP}), ["NET006"])

    def test_ignore_comment(self):
        h = GOOD_H.replace("    UFUNCTION(NetMulticast, Unreliable)",
                           "    // netlint:ignore NET003 보스 연출은 반드시 도착해야 함\n    UFUNCTION(NetMulticast, Reliable)")
        self.assertEqual(rules({"Hero.h": h}, {"Hero.cpp": GOOD_CPP}), [])

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "Intermediate"))
            with open(os.path.join(d, "Hero.h"), "w") as f:
                f.write(GOOD_H)
            with open(os.path.join(d, "Intermediate", "Gen.h"), "w") as f:
                f.write("UPROPERTY(Replicated) int32 Skipped;")
            self.assertEqual(lr.main([d]), 1)  # cpp가 없어 NET001
            with open(os.path.join(d, "Hero.cpp"), "w") as f:
                f.write(GOOD_CPP)
            self.assertEqual(lr.main([d, "--md", os.path.join(d, "r.md")]), 0)
        self.assertEqual(lr.main(["/nonexistent-dir"]), 2)


if __name__ == "__main__":
    unittest.main()
