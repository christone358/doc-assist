<script>
  export let name = '';
  export let className = '';
  export let style = '';
  export let title = '';
  export let spin = false;

  const ICON_MAP = {
    add: 'add',
    analytics: 'dashboard',
    apartment: 'organization',
    auto_awesome: 'sparkle-filled',
    auto_stories: 'book',
    bar_chart: 'graph-line',
    build: 'tools',
    chat_bubble: 'comment-discussion',
    check_circle: 'pass-filled',
    chevron_left: 'chevron-left',
    chevron_right: 'chevron-right',
    close: 'close',
    content_copy: 'copy',
    delete: 'trash',
    description: 'file-text',
    edit: 'edit',
    error: 'error',
    expand_less: 'chevron-up',
    expand_more: 'chevron-down',
    extension: 'extensions',
    extension_off: 'extensions',
    folder: 'folder',
    folder_open: 'folder-opened',
    help: 'question',
    history: 'history',
    hourglass_top: 'loading',
    info: 'info',
    left_click: 'cursor',
    lightbulb: 'lightbulb',
    menu_book: 'book',
    query_stats: 'pulse',
    save: 'save',
    search: 'search',
    send: 'send',
    settings: 'settings-gear',
    smart_toy: 'robot',
    star: 'star-full',
    stop_circle: 'stop-circle',
    sync: 'sync',
    task_alt: 'pass-filled',
    terminal: 'terminal',
    wifi: 'vm-connect',
  };

  $: codiconName = ICON_MAP[name] || 'circle-filled';
  $: classes = [
    'codicon',
    `codicon-${codiconName}`,
    spin ? 'codicon-modifier-spin' : '',
    className,
  ]
    .filter(Boolean)
    .join(' ');
</script>

<span class={classes} style={style} title={title} aria-hidden={title ? undefined : 'true'}></span>
