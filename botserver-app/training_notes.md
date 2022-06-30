# Trigger intent from custom action
https://forum.rasa.com/t/trigger-intent-from-custom-action/51727/6

# Rule data (Rule-based Policies)
Training data must declare condition (slot information), otherwise training machenisim will impose initinal slot information as condition (very implicit).  
This makes rules (were not declare condition) mostly uneffective in runtime because the condition mostly would have been changed.

# The presence of slot creates heavy shadow over all subsequent predictions
- This makes prediction in some cases is very suprising and intractable.  
- Slots was set many step before the prediction time but its presence might mislead algorithm learns wrong relationship  
- Try to minimize consecutive actions if there is not significant changes in systems' states.  
- This (perhasp) cuold be mitigated by increase number_of_negative_examples configuration (TED policy) but training's convergence will be severely affected.  

# Branching of scinario
- Branching makes less confidence, them more branches the more confused.
- Branching is very sensitive to quantity of sample, a few more sample (unbalance of same level branches) may easily cause wrong prediction (wrong confidence -> wrong choice)
(** There is no evidence showing that the algorithm's inteligence, haha! **)
