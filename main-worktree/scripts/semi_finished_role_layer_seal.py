"""Seal latest actual isolated ORM readback and relevant live read input fingerprint."""
import sys
from semi_finished_role_layer import ROOT, OUT, read, save, sha
sys.path.insert(0,str(ROOT/'backend'))
from pde.semi_finished_configuration_validation import formal_fingerprint
evidence=read('ISOLATED_REPLAY.json')
evidence['formalInputFingerprint']=formal_fingerprint(read('FORMAL_BEFORE.json')['formal'])
save('ISOLATED_REPLAY.json',evidence)
save('REPLAY_SEAL.json',{'sha256':sha(OUT/'ISOLATED_REPLAY.json'),'formalInputFingerprint':evidence['formalInputFingerprint']})
print(sha(OUT/'ISOLATED_REPLAY.json'))
