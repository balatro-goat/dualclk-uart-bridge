`timescale 1ns/1ps

module async_fifo #(
    parameter integer WIDTH = 8,
    parameter integer DEPTH = 16
)(
    input logic wr_clk,
    input logic wr_rst_n,
    input logic wr_en,
    input logic [WIDTH-1:0] wr_data,
    output logic full,

    input logic rd_clk,
    input logic rd_rst_n,
    input logic rd_en,
    output logic [WIDTH-1:0] rd_data,
    output logic rd_valid,
    output logic empty
);

    localparam integer ADDR_WIDTH = $clog2(DEPTH);
    localparam integer PTR_WIDTH = ADDR_WIDTH + 1;

    logic [WIDTH-1:0] mem [0:DEPTH-1];

    logic [PTR_WIDTH-1:0] wbin;
    logic [PTR_WIDTH-1:0] wbin_next;
    logic [PTR_WIDTH-1:0] wgray;
    logic [PTR_WIDTH-1:0] wgray_next;

    logic [PTR_WIDTH-1:0] rbin;
    logic [PTR_WIDTH-1:0] rbin_next;
    logic [PTR_WIDTH-1:0] rgray;
    logic [PTR_WIDTH-1:0] rgray_next;

    logic [PTR_WIDTH-1:0] rgray_wsync1;
    logic [PTR_WIDTH-1:0] rgray_wsync2;

    logic [PTR_WIDTH-1:0] wgray_rsync1;
    logic [PTR_WIDTH-1:0] wgray_rsync2;

    logic full_next;
    logic empty_next;

    //Caculate Gray code
    always @(*) begin
        wbin_next = wbin;

        if (wr_en && !full)
            wbin_next = wbin + 1'b1;
        
        wgray_next = wbin_next ^ (wbin_next >> 1);
    end

    always @(*) begin
        rbin_next = rbin;

        if (rd_en && !empty)
            rbin_next = rbin + 1'b1;
        
        rgray_next = rbin_next ^ (rbin_next >> 1);
    end

    //Full and Empty
    always @(*) begin
        empty_next = (rgray_next == wgray_rsync2);
    end

    always @(*) begin
        full_next = (
            wgray_next ==
            {
                ~rgray_wsync2[PTR_WIDTH-1:PTR_WIDTH-2],
                rgray_wsync2[PTR_WIDTH-3:0]
            }
        );
    end

    //Update next state
    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            wbin <= '0;
            wgray <= '0;
            full <= 1'b0;
        end
        else begin
           wbin <= wbin_next;
           wgray <= wgray_next; 
           full <= full_next;
        end
    end

    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            rbin <= '0;
            rgray <= '0;
            empty <= 1'b1;
        end
        else begin
            rbin <= rbin_next;
            rgray <= rgray_next;
            empty <= empty_next;
        end
    end

    //Sync
    always @(posedge wr_clk or negedge wr_rst_n) begin
        if (!wr_rst_n) begin
            rgray_wsync1 <= '0;
            rgray_wsync2 <= '0;
        end
        else begin
            rgray_wsync1 <= rgray;
            rgray_wsync2 <= rgray_wsync1;
        end
    end

    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            wgray_rsync1 <= '0;
            wgray_rsync2 <= '0;
        end
        else begin
            wgray_rsync1 <= wgray;
            wgray_rsync2 <= wgray_rsync1;
        end
    end

    //Write data
    always @(posedge wr_clk) begin
        if (wr_en && !full)
            mem[wbin[ADDR_WIDTH-1:0]] <= wr_data;
    end

    always @(posedge rd_clk or negedge rd_rst_n) begin
        if (!rd_rst_n) begin
            rd_data <= '0;
            rd_valid <= 1'b0;
        end
        else begin
            rd_valid <= rd_en && !empty;

            if (rd_en && !empty)
                rd_data <= mem[rbin[ADDR_WIDTH-1:0]];
        end
    end
        
endmodule