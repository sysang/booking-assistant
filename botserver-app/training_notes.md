# Trigger intent from custom action
https://forum.rasa.com/t/trigger-intent-from-custom-action/51727/6

# Rule data (Rule-based Policies)
Training data must declare condition (slot information), otherwise training machenisim will impose initinal slot information as condition (very implicit).  
This makes rules (were not declare condition) mostly uneffective in runtime because the condition mostly would have been changed.

# The presence of slot creates heavy shadow over all subsequent predictions (the shadow of slot)
- This makes prediction in some cases is very suprising and intractable.  
- Slots was set many step before the prediction time but its presence might mislead algorithm learns wrong relationship  
- Try to minimize consecutive actions if there is not significant changes in systems' states.  
- This (perhasp) cuold be mitigated by increase number_of_negative_examples configuration (TED policy) but training's convergence will be severely affected.  
- The shadow of slot at other scope will create very supprising affect.  

# Branching of scenario
- Branching makes less confidence, them more branches the more confused.
- Branching is very sensitive to quantity of sample, a few more sample (unbalance of same level branches) may easily cause wrong prediction (wrong confidence -> wrong choice)
(** There is no evidence showing that the algorithm's inteligence, haha! **)

# Algorithm architecture (via TED policy configurations) does take vital influence
- number_of_negative_examples, batch_size, connection_density does help -> mitigate negative effect of bias and shadow of slot.  

# Training Configuration (model architecture) do have vital importance
- Mind very veyr (x10) carefully on training improvment, it did exist a case when changing ted policy configuration flips thing from 'fail' to 'work'
- For instance, story 'jumpin_middle_query_hotel_room' worked after number_of_negative_examples had been changed from 50 to 73, connection_density had been changed from 0.37 to 0.41

# batch_size does help
- Evidence is the case when (batch_size: [17, 33], epochs: 1523) led to good performance but (batch_size: [17, 33], epochs: 2513) had different diagram (worse).
- Explain: because when change the number of epoch the structure of batch_size change occodringly. So with batch_size: [17, 43] the struture is preserved
