import sys
import json

import ROOT

if __name__ == "__main__":
    fp = ROOT.TFile.Open(sys.argv[1])
    for key in fp.GetListOfKeys():
        msg = {
            "key": key.GetName(),
            "class": key.GetClassName(),
        }
        print(json.dumps(msg))
        if msg["class"] == "RNTuple":
            pass
