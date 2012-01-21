'''
Reg Replace
Licensed under MIT
Copyright (c) 2011 Isaac Muse <isaacmuse@gmail.com>
'''

import sublime
import sublime_plugin
import re

DEFAULT_SHOW_PANEL = False
DEFAULT_HIGHLIGHT_COLOR = "invalid"
DEFAULT_HIGHLIGHT_STYLE = "outline"
DEFAULT_MULTI_PASS_MAX_SWEEP = 100
MODULE_NAME = "RegReplace"
rrsettings = sublime.load_settings('reg_replace.sublime-settings')


def underline(regions):
    # Convert to empty regions
    new_regions = []
    for region in regions:
        start = region.begin()
        end = region.end()
        while start < end:
            new_regions.append(sublime.Region(start))
            start += 1
    return new_regions


class RegReplaceInputCommand(sublime_plugin.WindowCommand):
    def run_sequence(self, value):
        find_only = False
        action = None
        multi_pass = False
        options = {}

        # Parse Input
        matches = re.match(r"(\?)?\s*([^\+][\w\W]*|\+?)\s*:\s*([\w\W]*)\s*", value)
        if matches != None:
            # Sequence
            value = matches.group(3)

            # Find Only?
            if matches.group(1) == "?":
                find_only = True

            # Multi-Pass?
            if matches.group(2) == "+":
                multi_pass = True

            # Action?
            elif matches.group(2) != '' and matches.group(2) != None:
                # Mark or unmark: parse options?
                params = re.match(r"^(unmark|mark)\s*=\s*([\w\s\.\-]*)\s*(?:,\s*([\w\s\.\-]*)\s*)?(?:,\s*([\w\s\.\-]*))?\s*", matches.group(2))
                if params != None:
                    if params.group(2) != '' and params.group(2) != None:
                        # Mark options
                        if params.group(1) == "mark":
                            options['key'] = params.group(2).strip()
                            if params.group(3) != '' and params.group(3) != None:
                                options['scope'] = params.group(3).strip()
                            if params.group(4) != '' and params.group(4) != None:
                                options['style'] = params.group(4).strip()
                            action = params.group(1)
                        # Unmark options
                        elif params.group(1) == "unmark":
                            options['key'] = params.group(2)
                            action = params.group(1)
                else:
                    # All other actions
                    action = matches.group(2)

        # Parse returned regex sequence
        sequence = [x.strip() for x in value.split(',')]
        view = self.window.active_view()

        # Execute sequence
        if view != None:
            view.run_command(
                'reg_replace',
                {
                    'replacements': sequence,
                    'find_only': find_only,
                    'action': action,
                    'multi_pass': multi_pass,
                    'options': options
                }
            )

    def run(self):
        # Display RegReplace input panel for on the fly regex sequences
        self.window.show_input_panel(
            "Regex Sequence:",
            "",
            self.run_sequence,
            None,
            None
        )


class RegReplaceCommand(sublime_plugin.TextCommand):
    handshake = None

    def forget_handshake(self):
        # Forget current view
        self.handshake = None
        self.clear_highlights(MODULE_NAME)

    def replace_prompt(self):
        # Ask if replacements are desired
        self.view.window().show_input_panel(
            "Replace targets / perform action? (yes | no):",
            "yes",
            self.run_replace,
            None,
            self.forget_handshake
        )

    def run_replace(self, answer):
        # Do we want to replace
        if answer.strip().lower() != "yes":
            self.forget_handshake()
            return

        # See if we know this view
        window = sublime.active_window()
        view = window.active_view() if window != None else None
        if view != None:
            if self.handshake != None and self.handshake == view.id():
                self.forget_handshake()
                # re-run command to actually replace targets
                view.run_command(
                    'reg_replace',
                    {
                        'replacements': self.replacements,
                        'action': self.action,
                        'multi_pass': self.multi_pass,
                        'options': self.options
                    }
                )
        else:
            self.forget_handshake()

    def set_highlights(self, key, style, color):
        # Process highlight style
        highlight_style = 0
        if style == "outline":
            highlight_style = sublime.DRAW_OUTLINED
        elif style == "underline":
            self.target_regions = underline(self.target_regions)
            highlight_style = sublime.DRAW_EMPTY_AS_OVERWRITE

        # higlight all of the found regions
        self.view.erase_regions(key)
        self.view.add_regions(
            key,
            self.target_regions,
            color,
            highlight_style
        )

    def clear_highlights(self, key):
        # Clear all highlighted regions
        self.view.erase_regions(key)

    def ignore_ending_newlines(self, regions):
        new_regions = []
        for region in regions:
            offset = 0
            size = region.size()
            if size > offset and self.view.substr(region.end() - 1) == "\n":
                offset += 1
            if size > offset and self.view.substr(region.end() - offset - 1) == "\r":
                offset += 1
            new_regions.append(sublime.Region(region.begin(), region.end() - offset))
        return new_regions

    def print_results_status_bar(self, text):
        sublime.status_message(text)

    def print_results_panel(self, text):
        # Get/create output panel
        window = self.view.window()
        view = window.get_output_panel('reg_replace_results')

        #Turn off stylings in panel
        view.settings().set("draw_white_space", "none")
        view.settings().set("draw_indent_guides", False)
        view.settings().set("gutter", "none")
        view.settings().set("line_numbers", False)
        view.set_syntax_file("Packages/Text/Plain text.tmLanguage")

        # Show Results in read only panel and clear selection in panel
        window.run_command("show_panel", {"panel": "output.reg_replace_results"})
        view.set_read_only(False)
        edit = view.begin_edit()
        view.replace(edit, sublime.Region(0, view.size()), "RegReplace Results\n\n" + text)
        view.end_edit(edit)
        view.set_read_only(True)
        view.sel().clear()

    def perform_action(self, action, options={}):
        status = True
        if action == "fold":
            self.target_regions = self.ignore_ending_newlines(self.target_regions)
            self.view.fold(self.target_regions)
        elif action == "unfold":
            for region in self.target_regions:
                self.view.unfold(region)
        elif action == "mark":
            if 'key' in options:
                color = options['scope'].strip() if 'scope' in options else DEFAULT_HIGHLIGHT_COLOR
                style = options['style'].strip() if 'style' in options else DEFAULT_HIGHLIGHT_STYLE
                self.set_highlights(options['key'].strip(), style, color)
        elif action == "unmark":
            if 'key' in options:
                self.clear_highlights(options['key'].strip())
        else:
            status = False
        return status

    def get_sel_point(self):
        # See if there is a cursor and get the first selections starting point
        sel = self.view.sel()
        pt = None if len(sel) == 0 else sel[0].begin()
        return pt

    def qualify_by_scope(self, region, pattern):
        for entry in pattern:
            # Is there something to qualify?
            if len(entry) > 0:
                # Initialize qualification parameters
                qualify = True
                pt = region.begin()
                end = region.end()

                # Disqualify if entirely of scope
                if entry.startswith("-!"):
                    entry = entry.lstrip("-!")
                    qualify = False
                    while pt < end:
                        if self.view.score_selector(pt, entry) == 0:
                            qualify = True
                            break
                        pt += 1
                # Disqualify if one or more instances of scope
                elif entry.startswith("-"):
                    entry = entry.lstrip("-")
                    while pt < end:
                        if self.view.score_selector(pt, entry):
                            qualify = False
                            break
                        pt += 1
                # Qualify if entirely of scope
                elif entry.startswith("!"):
                    entry = entry.lstrip("!")
                    while pt < end:
                        if self.view.score_selector(pt, entry) == 0:
                            qualify = False
                            break
                        pt += 1
                # Qualify if one or more instances of scope
                else:
                    qualify = False
                    while pt < end:
                        if self.view.score_selector(pt, entry):
                            qualify = True
                            break
                        pt += 1
                # If qualificatin of one fails, bail
                if qualify == False:
                    return qualify
        # Qualification completed successfully
        return True

    def greedy_replace(self, find, replace, regions, scope_filter):
        # Initialize replace
        replaced = 0
        count = len(regions) - 1

        # Step through all targets and qualify them for replacement
        for region in reversed(regions):
            # Does the scope qualify?
            qualify = self.qualify_by_scope(region, scope_filter) if scope_filter != None else True
            if qualify:
                replaced += 1
                if self.find_only or self.action != None:
                    # If "find only" or replace action is overridden, just track regions
                    self.target_regions.append(region)
                else:
                    # Apply replace
                    self.view.replace(self.edit, region, replace[count])
            count -= 1
        return replaced

    def non_greedy_replace(self, find, replace, regions, scope_filter):
        # Initialize replace
        replaced = 0
        last_region = len(regions) - 1
        selected_region = None
        selection_index = 0

        # See if there is a cursor and get the first selections starting point
        pt = self.get_sel_point()

        # Intialize with first qualifying region for wrapping and the case of no cursor in view
        count = 0
        for region in regions:
            # Does the scope qualify?
            qualify = self.qualify_by_scope(region, scope_filter) if scope_filter != None else True
            if qualify:
                # Update as new replacement candidate
                selected_region = region
                selection_index = count
                break
            else:
                count += 1

        # If regions were already swept till the end, skip calculation relative to cursor
        if selected_region != None and count < last_region and pt != None:
            # Try and find the first qualifying match contained withing the first selection or after
            reverse_count = last_region
            for region in reversed(regions):
                # Make sure we are not checking previously checked regions
                # And check if region contained after start of selection?
                if reverse_count >= count and region.end() - 1 >= pt:
                    # Does the scope qualify?
                    qualify = self.qualify_by_scope(region, scope_filter) if scope_filter != None else True
                    if qualify:
                        # Update as new replacement candidate
                        selected_region = region
                        selection_index = reverse_count
                    # Walk backwards through replace index
                    reverse_count -= 1
                else:
                    break

        # Did we find a suitable region?
        if selected_region != None:
            # Show Instance
            replaced += 1
            self.view.show(selected_region.begin())
            if self.find_only or self.action != None:
                # If "find only" or replace action is overridden, just track regions
                self.target_regions.append(selected_region)
            else:
                # Apply replace
                self.view.replace(self.edit, selected_region, replace[selection_index])
        return replaced

    def greedy_scope_replace(self, regions, re_find, replace, greedy_replace):
        total_replaced = 0
        try:
            for region in reversed(regions):
                string = self.view.substr(region)
                extraction, replaced = re.subn(re_find, replace, string) if greedy_replace else re.subn(re_find, replace, string, 1)
                if replaced > 0:
                    total_replaced += 1
                    if self.find_only or self.action != None:
                        self.target_regions.append(region)
                    else:
                        self.view.replace(self.edit, region, extraction)
        except Exception, err:
            sublime.error_message('REGEX ERROR: %s' % str(err))
            return total_replaced

        return total_replaced

    def non_greedy_scope_replace(self, regions, re_find, replace, greedy_replace):
        # Initialize replace
        total_replaced = 0
        replaced = 0
        last_region = len(regions) - 1
        selected_region = None
        selected_extraction = None

        # See if there is a cursor and get the first selections starting point
        pt = self.get_sel_point()

        # Intialize with first qualifying region for wrapping and the case of no cursor in view
        count = 0
        try:
            for region in regions:
                string = self.view.substr(region)
                extraction, replaced = re.subn(re_find, replace, string) if greedy_replace else re.subn(re_find, replace, string, 1)
                if replaced > 0:
                    selected_region = region
                    selected_extraction = extraction
                    break
                else:
                    count += 1
        except Exception, err:
            sublime.error_message('REGEX ERROR: %s' % str(err))
            return total_replaced

        try:
            # If regions were already swept till the end, skip calculation relative to cursor
            if selected_region != None and count < last_region and pt != None:
                # Try and find the first qualifying match contained withing the first selection or after
                reverse_count = last_region
                for region in reversed(regions):
                    # Make sure we are not checking previously checked regions
                    # And check if region contained after start of selection?
                    if reverse_count >= count and region.end() - 1 >= pt:
                        string = self.view.substr(region)
                        extraction, replaced = re.subn(re_find, replace, string) if greedy_replace else re.subn(re_find, replace, string, 1)
                        if replaced > 0:
                            selected_region = region
                            selected_extraction = extraction
                        reverse_count -= 1
                    else:
                        break
        except Exception, err:
            sublime.error_message('REGEX ERROR: %s' % str(err))
            return total_replaced

        # Did we find a suitable region?
        if selected_region != None:
            # Show Instance
            total_replaced += 1
            self.view.show(selected_region.begin())
            if self.find_only or self.action != None:
                # If "find only" or replace action is overridden, just track regions
                self.target_regions.append(selected_region)
            else:
                # Apply replace
                self.view.replace(self.edit, selected_region, selected_extraction)
        return total_replaced

    def scope_apply(self, pattern):
        replaced = 0
        regions = []

        scope = pattern['scope']
        find = pattern['find'] if 'find' in pattern else None
        replace = pattern['replace'] if 'replace' in pattern else "\\0"
        greedy_scope = bool(pattern['greedy_scope']) if 'greedy_scope' in pattern else True
        greedy_replace = bool(pattern['greedy_replace']) if 'greedy_replace' in pattern else True
        case = bool(pattern['case']) if 'case' in pattern else True
        # literal = bool(pattern['literal']) if 'literal' in pattern else False

        if scope == None or scope == '':
            return replace

        regions = self.view.find_by_selector(scope)
        # Find supplied?
        if find != None:
            # Regex replace
            if find != None:
                # Compile regex: Ignore case flag?
                try:
                    re_find = re.compile(find, re.IGNORECASE) if case else re.compile(find)
                except Exception, err:
                    sublime.error_message('REGEX ERROR: %s' % str(err))
                    return replaced

                #Greedy Scope?
                if greedy_scope:
                    replaced = self.greedy_scope_replace(regions, re_find, replace, greedy_replace)
                else:
                    replaced = self.non_greedy_scope_replace(regions, re_find, replace, greedy_replace)
        else:
            if greedy_scope:
                # Greedy scope; return all scopes
                replaced = len(regions)
                self.target_regions = regions
            else:
                # Non-greedy scope; return first valid scope
                # If cannot find first valid scope after cursor
                number_regions = len(regions)
                selected_region = None
                first_region = 0
                last_region = number_regions - 1
                pt = self.get_sel_point()

                # Find first scope
                if number_regions > 0:
                    selected_region = regions[0]

                # Walk backwards seeing which scope is valid
                # Quit if you reach the already selected first scope
                if selected_region != None and last_region > first_region and pt != None:
                    reverse_count = last_region
                    for region in reversed(regions):
                        if reverse_count >= first_region and region.end() - 1 >= pt:
                            selected_region = region
                            reverse_count -= 1
                        else:
                            break

                # Store the scope if we found one
                if selected_region != None:
                    replaced += 1
                    self.view.show(selected_region.begin())
                    self.target_regions = [selected_region]

        return replaced

    def apply(self, pattern):
        # Initialize replacement variables
        regions = []
        flags = 0
        replaced = 0

        # Grab pattern definitions
        find = pattern['find']
        replace = pattern['replace'] if 'replace' in pattern else "\\0"
        literal = bool(pattern['literal']) if 'literal' in pattern else False
        greedy = bool(pattern['greedy']) if 'greedy' in pattern else True
        case = bool(pattern['case']) if 'case' in pattern else True
        scope_filter = pattern['scope_filter'] if 'scope_filter' in pattern else []

        # Ignore Case?
        if not case:
            flags |= sublime.IGNORECASE

        # Literal find?
        if literal:
            flags |= sublime.LITERAL

        # Find and format replacements
        extractions = []
        try:
            regions = self.view.find_all(find, flags, replace, extractions)
        except Exception, err:
            sublime.error_message('REGEX ERROR: %s' % str(err))
            return replaced

        # Where there any regions found?
        if len(regions) > 0:
            # Greedy or non-greedy search? Get replaced instances.
            if greedy:
                replaced = self.greedy_replace(find, extractions, regions, scope_filter)
            else:
                replaced = self.non_greedy_replace(find, extractions, regions, scope_filter)
        return replaced

    def run(self, edit, replacements=[], find_only=False, clear=False, action=None, multi_pass=False, options={}):
        self.find_only = find_only
        self.action = action.strip() if action != None else action
        self.target_regions = []
        self.replacements = replacements
        self.multi_pass = multi_pass
        self.options = options

        # Clear regions and exit
        if clear:
            self.clear_highlights(MODULE_NAME)
            return
        elif action == "unmark" and "key" in options:
            self.perform_action(action, options)

        # Establish new run
        self.handshake = self.view.id()

        # Is the sequence empty?
        if len(replacements) > 0:
            replace_list = rrsettings.get('replacements', {})
            panel_display = rrsettings.get("results_in_panel", DEFAULT_SHOW_PANEL)
            result_template = "%s: %d regions;\n" if panel_display else "%s: %d regions; "
            self.edit = edit
            results = ""

            # Walk the sequence
            # Multi-pass only if requested and will be occuring
            if multi_pass and not find_only and action == None:
                # Multi-pass initialization
                current_replacements = 0
                total_replacements = 0
                count = 0
                max_sweeps = rrsettings.get('multi_pass_max_sweeps', DEFAULT_MULTI_PASS_MAX_SWEEP)

                # Sweep file until all instances are found
                # Avoid infinite loop and break out if sweep threshold is met
                while count < max_sweeps:
                    count += 1
                    current_replacements = 0

                    for replacement in replacements:
                        # Is replacement available in the list?
                        if replacement in replace_list:
                            pattern = replace_list[replacement]
                            # Search within a specific scope or search and qualify with scopes
                            if 'scope' in pattern:
                                current_replacements = self.scope_apply(pattern)
                            else:
                                current_replacements = self.apply(pattern)
                    total_replacements += current_replacements

                    # No more regions found?
                    if current_replacements == 0:
                        break
                # Record total regions found
                results += "Regions Found: %d regions;" % total_replacements
            else:
                for replacement in replacements:
                    # Is replacement available in the list?
                    if replacement in replace_list:
                        pattern = replace_list[replacement]
                        # Search within a specific scope or search and qualify with scopes
                        if 'scope' in pattern:
                            results += result_template % (replacement, self.scope_apply(pattern))
                        else:
                            results += result_template % (replacement, self.apply(pattern))

            # Higlight regions
            if self.find_only:
                style = rrsettings.get("find_highlight_style", DEFAULT_HIGHLIGHT_STYLE)
                color = rrsettings.get('find_highlight_color', DEFAULT_HIGHLIGHT_COLOR)
                self.set_highlights(MODULE_NAME, style, color)
                self.replace_prompt()
            else:
                # Perform action
                if action != None:
                    self.clear_highlights(MODULE_NAME)
                    if not self.perform_action(action, options):
                        results = "Error: Bad Action!"

                # Report results
                if panel_display:
                    self.print_results_panel(results)
                else:
                    self.print_results_status_bar(results)
