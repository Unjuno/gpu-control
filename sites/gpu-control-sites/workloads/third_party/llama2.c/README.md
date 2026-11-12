`run.c` is adapted from `karpathy/llama2.c` commit
`350e04fe35433e6d2941dce5a1f53308f87058eb` (MIT). Local source changes add
`<stdint.h>` for Debian compilation, define `-n` as a maximum *new* token
count, clamp total transformer steps to the model context, report the actual
sampled-token count on stderr, and remove the unused interactive chat mode. The
binary accepts only fixed generation arguments; its unused unsafe chat mode and
the `-m`/`-y` options are removed. Token concatenation uses bounded `snprintf`.

The locally reviewed `run.c` SHA-256 is
`78951c4623437da86cc5d835ea26af8c750c5132dfeb6e506c4a2db918e61682` and is
checked during image build. The model and tokenizer are independently pinned by
their exact upstream revisions and SHA-256 values in the inference Dockerfile.
