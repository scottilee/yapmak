Grunthal Handelsbank AG — codes & queues (case-sensitive, reason omitted exactly where listed "none").

Outcomes and reasons are fixed by clause 12 of the regulation. Allowed values:

  ghb-arranged:    (no reason)
  ghb-settled:     (no reason)
  ghb-transferred: ghb-rework | ghb-person
  ghb-no-deal:     ghb-refuse | ghb-distress | ghb-dispute | ghb-R07
  ghb-unverified:  ghb-failed | ghb-declined
  ghb-unreached:   ghb-cb | ghb-no-cb | ghb-wrong | ghb-deceased | ghb-unclear

Transfer queues (used by clause 10): ghb-rework, ghb-desk.
Note reasons (used by clause 11.1): ghb-refuse, ghb-distress, ghb-dispute, ghb-cleared, ghb-R07.

Floor fields by clause (clause 6.2): darlehen -> tilgung_min; kontokorrent -> kk_min; leasing -> l_min; kreditkarte -> kk_min; hypothek -> h_min.