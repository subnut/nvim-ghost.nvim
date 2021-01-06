# nvim-ghost.nvim

This is a neovim-only plugin for
[GhostText](https://github.com/GhostText/GhostText)

## Installation

Install it using your favourite plugin manager, and execute
`:call nvim_ghost#installer#install()`  
E.g. for [vim-plug](https://github.com/junegunn/vim-plug) -

```vim
Plug 'subnut/nvim-ghost.nvim', {'do': ':call nvim_ghost#installer#install()'}
```

:warning: **NOTE:** After installing for the first time, you need to restart
neovim for the plugin to start properly

## Usage

- Open neovim
- Use GhostText

Really, it's _that_ simple!

## Features

- **Zero** dependencies! Does not even need python installed!
- Supports Linux, macOS, **Windows**
- Supports **neovim running inside WSL** (Windows Subsystem for Linux)

## Customization

### Specifying a different port

The default is `4001`, which corresponds to the default value set in the browser
extension. If you want to use a different value, simply add the following line
to your `init.vim` -

```vim
let $GHOSTTEXT_SERVER_PORT = 4001
```

Replace `4001` with the port number you have set in the browser extension

### Custom settings according to website

When you trigger GhostText, nvim-ghost triggers an `User` autocommand. You can
listen for that autocommand and run your own commands (e.g. setting filetype)

**NOTE:** All the autocommands should be in the `nvim_ghost_user_autocommands`
augroup

Some examples -

```vim
" Autocommand for a single website (i.e. stackoverflow.com)
au nvim_ghost_user_autocommands User www.stackoverflow.com set filetype=markdown

" Autocommand for a multiple websites
au nvim_ghost_user_autocommands User www.reddit.com,www.github.com set filetype=markdown

" Autocommand for a domain (i.e. github.com)
au nvim_ghost_user_autocommands User *github.com set filetype=markdown

" Multiple autocommands can be specified like so -
augroup nvim_ghost_user_autocommands
  au User www.reddit.com,www.stackoverflow.com set filetype=markdown
  au User www.reddit.com,www.github.com set filetype=markdown
  au User *github.com set filetype=markdown
augroup END
```
