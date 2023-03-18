<h1 align="center"><b><u><tt>nvim-ghost.nvim</tt></u></b></h1>

This is a neovim-only plugin for
[GhostText](https://github.com/GhostText/GhostText)

# Installation

Install it using your favourite plugin manager, e.g. for [vim-plug](https://github.com/junegunn/vim-plug) -

```vim
Plug 'subnut/nvim-ghost.nvim'
```

# Usage

- Open neovim
- Use GhostText

Really, it's _that_ simple!

# Features

- **Zero** dependencies! Does not even need python installed!
- Supports **neovim running inside WSL** (Windows Subsystem for Linux)
- Supports Linux, macOS, **Windows** out-of-the-box (_for other OSes, please see [below](#other_oses)_)

# Customization

## Specifying a different port

The default is `4001`, which corresponds to the default value set in the browser
extension. If you want to use a different value, simply add the following line
to your `init.vim` -

```vim
let g:nvim_ghost_server_port = 4001
```

Replace `4001` with the port number you have set in the browser extension

## Custom settings according to website

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

## Suppressing all messages

If you want to suppress _all_ messages from nvim-ghost, then add the following
to your `init.vim` -
```vim
let g:nvim_ghost_super_quiet = 1
```

## Start manually
:warning: **EXPERIMENTAL:** hasn't been tested thoroughly  
Add this line to your `init.vim` -
```vim
let g:nvim_ghost_autostart = 0
```
and then, when you need the plugin, run `:GhostTextStart` to enable the plugin for that specific neovim instance.

## Disable the plugin
If, for any reason, you want to disable the plugin completely, add this to your `init.vim` -
```vim
let g:nvim_ghost_disabled = 1
```
<br>

<h1 id="other_oses">Other Operating Systems</h1>
Please understand my situation. This plugin primarily uses a binary with it's
own packaged version of python3 and comes with the required packages
pre-installed, but the binary itself needs to be made on a machine running the
same OS as the target machine. (i.e. the Linux binary needs to be built on a
Linux machine, macOS binary on macOS, etc.)

The binaries are made using GitHub Actions, which only provides Linux, Windows
and macOS containers. So, it is impossible for me to distribute binaries for
other OSes.

So, to use this plugin, you shall need to install python3 (with pip) in your
system. Then, head off to this plugin's directory, and run -
```
python -m pip install -r requirements.txt
```
This needs to be done only once. This command installs the required packages
from pip.

Next, add the following two lines to your `init.vim` -
```vim
let g:nvim_ghost_use_script = 1
let g:nvim_ghost_python_executable = '/usr/bin/python'
```
Replace `/usr/bin/python` with the absolute path of the python executable
installed in your system. Now, restart neovim, and the plugin should work.

If you face any problems, please open an issue. I will try my best to work out
a solution for you.
