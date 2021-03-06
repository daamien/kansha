$(function() {
  $('.checklists').sortable({
    placeholder: "ui-state-highlight",
    axis: "y",
    handle: ".icon-list",
    cursor: "move",
    stop: function( event, ui ) { reorder_checklists($('.checklist').map(function() { return this.id; }).get()); }
  });
  $(".checklists .checklist .content ul").sortable({
      placeholder: "ui-state-highlight",
      cursor: "move",
      connectWith: ".checklists .checklist .content ul",
      dropOnEmpty: true,
      handle: "i",
      update: function(event, ui) {
          var data = {
              target: ui.item.closest('.checklist').attr('id'),
              index: ui.item.index(),
              id: ui.item.attr('id')
          };
          reorder_checklists_items(data);
      }
  }).disableSelection();
});