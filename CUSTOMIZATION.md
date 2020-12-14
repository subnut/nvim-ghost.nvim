# Specifying a different server port

The default is `4001`, which corresponds to the default value set in the
browser extension. If you want to use a different value, simply add the
following line to your `init.vim` -

```vim
let $GHOSTTEXT_SERVER_PORT = 4001
```
Replace `4001` with your choice of port number


# Custom settings according to website

When you trigger GhostText, nvim-ghost triggers an `User` autocommand. You
can listen for that autocommand and run your own commands (e.g. setting
filetype)

**NOTE:** All the autocommands should be in the
`nvim_ghost_user_autocommands` augroup

Some examples -

```vim
" Autocommand for a single website (i.e. stackoverflow.com)
au nvim_ghost_user_autocommands User stackoverflow.com set filetype=markdown

" Autocommand for a multiple websites
au nvim_ghost_user_autocommands User reddit.com,github.com set filetype=markdown

" Autocommand for a domain (i.e. github.com)
au nvim_ghost_user_autocommands User *github.com set filetype=markdown

" Multiple autocommands can be specified like so -
augroup nvim_ghost_user_autocommands
  au User reddit.com,stackoverflow.com set filetype=markdown
  au User reddit.com,github.com set filetype=markdown
  au User *github.com set filetype=markdown
augroup END
```
